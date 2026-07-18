"""User-submitted screenshot inspiration → private Taste RAG.

POST /api/inspiration/screenshot — multipart image upload (auth required).
Does NOT write to the shared trending catalog.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import User, UserInspirationCapture, get_db
from app.models.schemas import InspirationScreenshotResponse
from app.observability import atraced
from app.services.inspiration_screenshot import capture_out, process_screenshot

router = APIRouter(prefix="/api/inspiration", tags=["inspiration"])

_PRIVACY_NOTE = (
    "Your screenshot is analyzed once and not stored. Only planning facts "
    "extracted for your account are saved — never added to the public catalog."
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
