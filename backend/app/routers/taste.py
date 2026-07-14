"""Taste profile: view / edit / feedback — transparency + the §10 feedback loop.

- GET  /api/taste            → what the system thinks you like (+ editable snippets)
- POST /api/taste            → add a manual taste snippet ("I love bookstores")
- DELETE /api/taste/{id}     → forget a stored snippet (privacy: user controls it)
- POST /api/taste/feedback   → post-activity feedback → updates the taste profile
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import TasteSnippet, User, get_db
from app.models.schemas import (
    ExperienceFeedbackRequest,
    OkResponse,
    TasteAddRequest,
    TasteProfileOut,
    TasteSnippetOut,
)
from app.services.taste_profile import build_taste_profile, invalidate, record_snippet

router = APIRouter(prefix="/api/taste", tags=["taste"])


async def _profile_out(db: Session, user: User) -> TasteProfileOut:
    profile = await build_taste_profile(db, user)
    stored = db.scalars(
        select(TasteSnippet)
        .where(TasteSnippet.user_id == user.id)
        .order_by(TasteSnippet.created_at.desc())
    ).all()
    return TasteProfileOut(
        likes=profile.likes,
        dislikes=profile.dislikes,
        n_signals=profile.n_signals,
        snippets=[
            TasteSnippetOut(id=s.id, text=s.text, source=s.source, polarity=s.polarity)
            for s in stored
        ],
    )


@router.get("", response_model=TasteProfileOut)
async def get_taste(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return await _profile_out(db, user)


@router.post("", response_model=TasteProfileOut)
async def add_taste(
    body: TasteAddRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="text required")
    polarity = 1.0 if body.polarity >= 0 else -1.0
    record_snippet(db, user, body.text, source="manual", weight=1.2, polarity=polarity)
    invalidate(user.id)
    return await _profile_out(db, user)


@router.delete("/{snippet_id}", response_model=TasteProfileOut)
async def delete_taste(
    snippet_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.get(TasteSnippet, snippet_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Snippet not found")
    db.delete(row)
    db.commit()
    invalidate(user.id)
    return await _profile_out(db, user)


_VERDICTS = {
    "like": ("enjoyed {name}", 1.0, 1.0),
    "dislike": ("did not enjoy {name}", 1.0, -1.0),
    "again": ("would happily return to {name}", 1.2, 1.0),
    "crowded": ("found {name} too crowded", 1.0, -1.0),
}


@router.post("/feedback", response_model=OkResponse)
async def experience_feedback(
    body: ExperienceFeedbackRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Post-activity feedback → taste snippets (the §10 feedback loop)."""
    name = body.name.strip()
    if not name or body.verdict not in _VERDICTS:
        raise HTTPException(status_code=422, detail="name and valid verdict required")
    template, weight, polarity = _VERDICTS[body.verdict]
    record_snippet(db, user, template.format(name=name), source="feedback", weight=weight, polarity=polarity)
    if body.verdict == "crowded":
        # Generalize the signal so future ranking avoids crowded spots.
        record_snippet(db, user, "prefers calm, less crowded places", source="feedback", weight=0.8, polarity=-1.0)
    invalidate(user.id)
    return OkResponse(ok=True)
