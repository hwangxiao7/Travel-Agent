"""Beta feedback: store user feedback (DB) + email an alert, plus a guarded read.

Feedback is persisted to the DB so it survives redeploys, and (best-effort) an
email alert is sent to `settings.feedback_alert_email` for every submission. A
read-only admin endpoint returns recent feedback when the correct admin token is
supplied.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import BetaFeedback, get_db

router = APIRouter(prefix="/api/beta", tags=["beta"])


class BetaFeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    note: str = Field(default="", max_length=2000)
    query: str = Field(default="", max_length=500)
    destination: str = Field(default="", max_length=200)
    page: str = Field(default="web", max_length=64)
    user_email: str = Field(default="", max_length=255)


class BetaFeedbackOut(BaseModel):
    ok: bool = True


class FeedbackItem(BaseModel):
    id: int
    ts: str
    rating: int
    note: str
    query: str
    destination: str
    page: str
    user_email: str


@router.post("/feedback", response_model=BetaFeedbackOut)
def submit_beta_feedback(
    body: BetaFeedbackIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> BetaFeedbackOut:
    row = BetaFeedback(
        rating=body.rating,
        note=body.note.strip(),
        query=body.query.strip(),
        destination=body.destination.strip(),
        page=body.page.strip() or "web",
        user_email=body.user_email.strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    fb = {
        "ts": row.created_at.replace(tzinfo=timezone.utc).isoformat(),
        "rating": row.rating,
        "note": row.note,
        "query": row.query,
        "destination": row.destination,
        "page": row.page,
        "user_email": row.user_email,
    }
    # Email alert after the response is sent (never blocks / breaks submission).
    from app.services.notify import notify_feedback

    background_tasks.add_task(notify_feedback, fb)
    return BetaFeedbackOut(ok=True)


@router.get("/feedback", response_model=list[FeedbackItem])
def list_beta_feedback(
    limit: int = 100,
    x_admin_token: str = Header(default=""),
    db: Session = Depends(get_db),
) -> list[FeedbackItem]:
    """Read recent feedback. Guarded by the ADMIN_TOKEN (X-Admin-Token header)."""
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="forbidden")
    rows = db.scalars(
        select(BetaFeedback).order_by(BetaFeedback.created_at.desc()).limit(min(limit, 500))
    ).all()
    return [
        FeedbackItem(
            id=r.id,
            ts=r.created_at.replace(tzinfo=timezone.utc).isoformat(),
            rating=r.rating,
            note=r.note,
            query=r.query,
            destination=r.destination,
            page=r.page,
            user_email=r.user_email,
        )
        for r in rows
    ]
