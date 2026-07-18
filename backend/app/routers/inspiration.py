"""User-submitted screenshot inspiration → private Taste RAG + optional crowd signals.

POST /api/inspiration/screenshot — multipart image upload (auth required).
Layer A: private capture always. Layer B/C: anonymous signals unless crowd_opt_out.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.db import User, UserInspirationCapture, get_db
from app.models.schemas import (
    InspirationCrowdPickOut,
    InspirationCrowdPicksResponse,
    InspirationScreenshotResponse,
)
from app.observability import atraced
from app.services.inspiration_screenshot import capture_out, process_screenshot
from app.services.inspiration_signals import crowd_picks_for_user

router = APIRouter(prefix="/api/inspiration", tags=["inspiration"])

_PRIVACY_NOTE = (
    "Your screenshot is analyzed once and not stored. Layer A (private): planning facts "
    "and taste snippets stay on your account only. Layer B (optional): if you have not "
    "opted out of crowd signals, we log anonymous persona-tagged saves (activity/place keys, "
    "not your image or post text) so similar travelers can see aggregated picks after "
    "k-anonymity (≥3 users). Layer C: place names with coordinates may enter the shared "
    "catalog only after enough independent nominations and geocoding — facts only, no captions."
)


@router.post("/screenshot", response_model=InspirationScreenshotResponse)
async def inspiration_screenshot(
    image: UploadFile = File(...),
    language: str = Form(default="en"),
    origin_lat: float = Form(default=0.0),
    origin_lng: float = Form(default=0.0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Extract activity, place, timing, and must-know tips from a user screenshot."""
    async with atraced("/api/inspiration/screenshot"):
        raw = await image.read()
        mime = image.content_type or "image/jpeg"
        try:
            capture = await process_screenshot(
                db,
                user,
                image_bytes=raw,
                mime=mime,
                language=language,
                origin_lat=origin_lat,
                origin_lng=origin_lng,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return InspirationScreenshotResponse(ok=True, capture=capture)


@router.get("/privacy-note")
def inspiration_privacy_note() -> dict:
    return {"note": _PRIVACY_NOTE}


@router.get("/crowd-picks", response_model=InspirationCrowdPicksResponse)
def inspiration_crowd_picks(
    lat: float = 0.0,
    lng: float = 0.0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Layer B: persona + geo crowd picks from inspiration saves (k-anonymous)."""
    if getattr(user, "crowd_opt_out", False):
        return InspirationCrowdPicksResponse(
            picks=[],
            k_anonymity=settings.inspiration_nomination_k,
            note="Crowd signals disabled on your account.",
        )
    raw = crowd_picks_for_user(db, user, lat=lat, lng=lng)
    picks = [InspirationCrowdPickOut(**row) for row in raw]
    return InspirationCrowdPicksResponse(
        picks=picks,
        k_anonymity=settings.inspiration_nomination_k,
        note=_PRIVACY_NOTE,
    )


@router.get("/captures")
def list_captures(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(UserInspirationCapture)
        .where(UserInspirationCapture.user_id == user.id)
        .order_by(UserInspirationCapture.created_at.desc())
        .limit(40)
    ).all()
    return {"captures": [capture_out(r) for r in rows]}
