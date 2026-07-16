"""Persistent, evolving Taste Profile — the "我知道你喜欢什么" brain.

Product north star: *know what the user likes, then help them decide what to do
today.* This module is the first half. It turns a user's accumulated signals
into a single **taste vector** used to personalize discovery + planning.

Design principles (consistent with architecture doc §2.2):
- Open vocabulary: taste is stored as free-form natural-language snippets and
  understood via embeddings — NOT a maintained keyword/tag table.
- Persistent + evolving: snippets live in the DB and accrue over time; older
  ones DECAY so the profile tracks who the user is *now*.
- Zero-write bootstrap: existing reviews / trips / feedback are derived into
  snippets on read, so a profile exists before any new write path is added.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import FeedbackEvent, PlaceReview, TasteSnippet, Trip, User
from app.services.embeddings import Vector, embed_texts

# Exponential decay: a snippet's influence halves every HALF_LIFE_DAYS.
_HALF_LIFE_DAYS = 120.0
_FEEDBACK_LIKE = {"save", "visit", "share", "like"}


@dataclass
class Snippet:
    text: str
    weight: float
    polarity: float  # +1 like / -1 dislike
    age_days: float


@dataclass
class TasteProfile:
    vector: Vector | None  # weighted, decayed mean of snippet embeddings
    likes: list[str]  # top positive snippets (for reasons / prompt)
    dislikes: list[str]
    n_signals: int


def record_snippet(
    db: Session, user: User, text: str, *, source: str, weight: float = 1.0, polarity: float = 1.0
) -> None:
    """Persist one free-form taste signal (idempotent-ish: skips exact recent dup)."""
    text = (text or "").strip()
    if not text:
        return
    recent = db.scalars(
        select(TasteSnippet)
        .where(TasteSnippet.user_id == user.id, TasteSnippet.source == source)
        .order_by(TasteSnippet.created_at.desc())
        .limit(5)
    ).all()
    if any(s.text.strip().lower() == text.lower() for s in recent):
        return
    db.add(
        TasteSnippet(
            user_id=user.id, text=text[:400], source=source, weight=weight, polarity=polarity
        )
    )
    db.commit()


def _history_snippets(db: Session, user: User) -> list[Snippet]:
    """Derive taste snippets from existing signals (no new writes needed)."""
    now = datetime.utcnow()
    out: list[Snippet] = []

    def age(dt: datetime) -> float:
        return max(0.0, (now - dt).total_seconds() / 86400.0)

    for r in db.scalars(select(PlaceReview).where(PlaceReview.user_id == user.id)).all():
        if r.rating >= 4:
            txt = f"enjoys {r.place_name}" + (f": {r.comment}" if r.comment else "")
            out.append(Snippet(txt, 1.2, 1.0, age(r.updated_at)))
        elif r.rating <= 2:
            out.append(Snippet(f"dislikes {r.place_name}", 1.0, -1.0, age(r.updated_at)))

    for t in db.scalars(select(Trip).where(Trip.user_id == user.id)).all():
        places = ""
        try:
            places = ", ".join(json.loads(t.places_json or "[]")[:6])
        except json.JSONDecodeError:
            pass
        txt = f"visited {t.destination}" + (f" ({places})" if places else "")
        out.append(Snippet(txt, 0.7, 1.0, age(t.created_at)))

    for e in db.scalars(select(FeedbackEvent).where(FeedbackEvent.user_id == user.id)).all():
        label = e.place_name or e.destination
        if not label:
            continue
        if e.event_type in _FEEDBACK_LIKE:
            out.append(Snippet(f"saved {label}", 0.8, 1.0, age(e.created_at)))
        elif e.event_type == "skip":
            out.append(Snippet(f"skipped {label}", 0.6, -1.0, age(e.created_at)))
        elif e.event_type == "rate":
            pol = 1.0 if (e.value or 3) >= 3.5 else -1.0
            out.append(Snippet(f"rated {label}", 0.6, pol, age(e.created_at)))
    return out


def _stored_snippets(db: Session, user: User) -> list[Snippet]:
    now = datetime.utcnow()
    rows = db.scalars(select(TasteSnippet).where(TasteSnippet.user_id == user.id)).all()
    return [
        Snippet(
            s.text,
            s.weight,
            s.polarity,
            max(0.0, (now - s.created_at).total_seconds() / 86400.0),
        )
        for s in rows
    ]


def _effective_weight(s: Snippet) -> float:
    decay = 0.5 ** (s.age_days / _HALF_LIFE_DAYS)
    return s.weight * decay


# Small in-process cache: {user_id: (signature, TasteProfile)}
_CACHE: dict[int, tuple[tuple, TasteProfile]] = {}


def _signature(snips: list[Snippet]) -> tuple:
    return (len(snips), round(sum(s.weight for s in snips), 2))


async def build_taste_profile(db: Session, user: User) -> TasteProfile:
    """Assemble the user's taste vector (weighted, decayed) + top snippets."""
    snips = _stored_snippets(db, user) + _history_snippets(db, user)
    if not snips:
        return TasteProfile(vector=None, likes=[], dislikes=[], n_signals=0)

    sig = _signature(snips)
    cached = _CACHE.get(user.id)
    if cached and cached[0] == sig:
        return cached[1]

    # Only positive snippets shape the "what to seek" vector; dislikes inform reasons.
    positives = [s for s in snips if s.polarity >= 0]
    vecs = await embed_texts([s.text for s in positives]) if positives else None

    vector: Vector | None = None
    if vecs:
        dim = len(vecs[0])
        acc = [0.0] * dim
        wsum = 0.0
        for s, v in zip(positives, vecs):
            w = _effective_weight(s)
            wsum += w
            for i in range(dim):
                acc[i] += w * v[i]
        if wsum > 0:
            norm = math.sqrt(sum(x * x for x in acc)) or 1.0
            vector = [x / norm for x in acc]

    likes = [
        s.text for s in sorted(
            (s for s in snips if s.polarity >= 0), key=_effective_weight, reverse=True
        )[:6]
    ]
    dislikes = [
        s.text for s in sorted(
            (s for s in snips if s.polarity < 0), key=_effective_weight, reverse=True
        )[:4]
    ]
    profile = TasteProfile(vector=vector, likes=likes, dislikes=dislikes, n_signals=len(snips))
    _CACHE[user.id] = (sig, profile)
    return profile


def invalidate(user_id: int) -> None:
    _CACHE.pop(user_id, None)
