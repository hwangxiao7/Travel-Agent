"""Batch double-tap likes → taste RAG (feature used by Surprise me + Trip planner)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import User, get_db
from app.models.schemas import Location
from app.services.likes import apply_like_batch

router = APIRouter(prefix="/api/likes", tags=["likes"])


class LikeItem(BaseModel):
    op: str  # like | unlike
    kind: str = "activity"  # activity | destination
    key: str
    name: str = ""
    tags: list[str] = Field(default_factory=list)
    blurb: str = ""
    highlight: str = ""
    reason: str = ""


class LikeBatchRequest(BaseModel):
    items: list[LikeItem] = Field(default_factory=list, max_length=40)
    origin: Location | None = None


class LikeBatchResponse(BaseModel):
    ok: bool = True
    liked: int = 0
    unliked: int = 0


@router.post("/batch", response_model=LikeBatchResponse)
def likes_batch(
    body: LikeBatchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not body.items:
        return LikeBatchResponse(ok=True)
    origin = body.origin
    result = apply_like_batch(
        db,
        user,
        items=[i.model_dump() for i in body.items],
        origin_label=(origin.label if origin else "") or "",
        origin_lat=origin.lat if origin else 0.0,
        origin_lng=origin.lng if origin else 0.0,
    )
    return LikeBatchResponse(ok=True, liked=result["liked"], unliked=result["unliked"])
