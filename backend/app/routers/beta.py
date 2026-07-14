"""Anonymous beta feedback for the web testing build (no login required)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/beta", tags=["beta"])

_FEEDBACK_PATH = Path(__file__).resolve().parents[3] / "data" / "beta_feedback.jsonl"


class BetaFeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    note: str = Field(default="", max_length=2000)
    query: str = Field(default="", max_length=500)
    destination: str = Field(default="", max_length=200)
    page: str = Field(default="web", max_length=64)


class BetaFeedbackOut(BaseModel):
    ok: bool = True


@router.post("/feedback", response_model=BetaFeedbackOut)
def submit_beta_feedback(body: BetaFeedbackIn) -> BetaFeedbackOut:
    _FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "rating": body.rating,
        "note": body.note.strip(),
        "query": body.query.strip(),
        "destination": body.destination.strip(),
        "page": body.page.strip() or "web",
    }
    with _FEEDBACK_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return BetaFeedbackOut(ok=True)
