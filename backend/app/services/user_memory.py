"""User-memory RAG: trips / reviews / prefs as retrievable documents.

Interview framing (搜广推):
- 搜 (Search): query ↔ destination relevance
- 广 (Explore): novelty / diversity vs past trips
- 推 (Push): personalized affinity from retrieved user memories
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import PlaceReview, Trip, User
from app.services.embeddings import Vector, embed_query, embed_texts
from app.services.personalization import UserProfile, build_user_profile

_TOKEN_RE = re.compile(r"[a-z0-9\u4e00-\u9fff]+", re.I)


@dataclass
class MemoryDoc:
    id: str
    kind: str  # trip | review_like | review_dislike | preference
    text: str
    destination: str = ""
    place_name: str = ""
    rating: int | None = None
    weight: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MemoryHit:
    doc: MemoryDoc
    score: float


@dataclass
class UserMemoryContext:
    profile: UserProfile
    memories: list[MemoryDoc] = field(default_factory=list)
    retrieved: list[MemoryHit] = field(default_factory=list)
    # dest → affinity in [-0.3, 0.4] from memory RAG
    affinity: dict[str, float] = field(default_factory=dict)
    # dest → visit count
    visit_counts: dict[str, int] = field(default_factory=dict)
    past_tags: list[str] = field(default_factory=list)
    memory_blocks: list[str] = field(default_factory=list)
    rewrite_hint: str = ""

    def to_dict(self) -> dict:
        return {
            "profile": self.profile.to_dict(),
            "retrieved": [
                {"id": h.doc.id, "kind": h.doc.kind, "score": round(h.score, 3), "text": h.doc.text[:160]}
                for h in self.retrieved
            ],
            "affinity": {k: round(v, 3) for k, v in self.affinity.items()},
            "visit_counts": self.visit_counts,
            "past_tags": self.past_tags,
            "rewrite_hint": self.rewrite_hint,
            "memory_blocks": self.memory_blocks,
        }


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _cosine(a: Vector, b: Vector) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def build_memory_corpus(db: Session, user: User) -> list[MemoryDoc]:
    """Materialize user history as RAG documents."""
    profile = build_user_profile(db, user)
    docs: list[MemoryDoc] = []

    trips = db.scalars(select(Trip).where(Trip.user_id == user.id).order_by(Trip.created_at.desc())).all()
    for t in trips:
        places: list[str] = []
        try:
            places = json.loads(t.places_json or "[]")
        except json.JSONDecodeError:
            places = []
        text = (
            f"Past trip to {t.destination} ({t.travel_mode}). "
            f"Dates {t.start_date or '?'}–{t.end_date or '?'}. "
            f"Summary: {t.summary or 'n/a'}. "
            f"Places: {', '.join(places) or 'n/a'}."
        )
        docs.append(
            MemoryDoc(
                id=f"trip:{t.id}",
                kind="trip",
                text=text,
                destination=t.destination,
                weight=1.0,
            )
        )

    reviews = db.scalars(
        select(PlaceReview).where(PlaceReview.user_id == user.id).order_by(PlaceReview.updated_at.desc())
    ).all()
    for r in reviews:
        kind = "review_like" if r.rating >= 4 else ("review_dislike" if r.rating <= 2 else "review")
        polarity = "loved" if r.rating >= 4 else ("disliked" if r.rating <= 2 else "rated")
        text = (
            f"User {polarity} {r.place_name} at {r.destination or 'unknown'} "
            f"({r.rating}/5). Comment: {r.comment or 'n/a'}."
        )
        weight = 1.2 if r.rating >= 4 else (0.9 if r.rating <= 2 else 0.6)
        docs.append(
            MemoryDoc(
                id=f"review:{r.id}",
                kind=kind,
                text=text,
                destination=r.destination or "",
                place_name=r.place_name,
                rating=r.rating,
                weight=weight,
            )
        )

    if profile.profile_text and "none yet" not in profile.profile_text.lower():
        docs.append(
            MemoryDoc(
                id=f"pref:{user.id}",
                kind="preference",
                text=profile.profile_text,
                weight=1.1,
            )
        )
    return docs


async def retrieve_user_memories(
    db: Session,
    user: User,
    query: str,
    *,
    k: int = 5,
) -> UserMemoryContext:
    """Retrieve query-relevant user memories and derive push/explore signals."""
    profile = build_user_profile(db, user)
    memories = build_memory_corpus(db, user)

    visit_counts: dict[str, int] = {}
    for m in memories:
        if m.kind == "trip" and m.destination:
            visit_counts[m.destination] = visit_counts.get(m.destination, 0) + 1

    past_tags = list(profile.activity_preferences)

    if not memories:
        return UserMemoryContext(profile=profile, visit_counts=visit_counts, past_tags=past_tags)

    qtok = _tokens(query)
    qvec = await embed_query(query)
    mem_vecs = await embed_texts([m.text for m in memories]) if qvec is not None else None

    hits: list[MemoryHit] = []
    for i, m in enumerate(memories):
        mtok = _tokens(m.text)
        kw = len(qtok & mtok) / (len(qtok) or 1)
        sem = _cosine(qvec, mem_vecs[i]) if qvec is not None and mem_vecs is not None else 0.0
        score = (0.55 * sem + 0.45 * kw) * m.weight if qvec is not None else kw * m.weight
        # Always keep strong like/dislike even if lexical overlap is weak.
        if m.kind == "review_like":
            score = max(score, 0.15 * m.weight)
        if m.kind == "review_dislike":
            score = max(score, 0.12 * m.weight)
        hits.append(MemoryHit(doc=m, score=score))

    hits.sort(key=lambda h: h.score, reverse=True)
    top = [h for h in hits if h.score > 0.05][:k]
    if not top:
        top = hits[: min(3, len(hits))]

    affinity: dict[str, float] = {}
    for h in top:
        dest = h.doc.destination
        if not dest:
            continue
        delta = 0.0
        if h.doc.kind == "review_like":
            delta = 0.12 + 0.08 * h.score
        elif h.doc.kind == "review_dislike":
            delta = -(0.15 + 0.1 * h.score)
        elif h.doc.kind == "trip":
            delta = 0.04 + 0.04 * h.score
        affinity[dest] = affinity.get(dest, 0.0) + delta

    # Soft affinity: liked place names overlapping destination catalog names
    for h in top:
        if h.doc.kind == "review_like" and h.doc.place_name:
            affinity[f"__place__:{h.doc.place_name.lower()}"] = (
                affinity.get(f"__place__:{h.doc.place_name.lower()}", 0.0) + 0.06
            )

    blocks = [f"[memory:{h.doc.kind}] {h.doc.text}" for h in top[:4]]
    # Compact rewrite hint from retrieved memories (not the whole profile dump).
    hint_bits = []
    for h in top[:3]:
        if h.doc.kind == "review_like":
            hint_bits.append(f"liked {h.doc.place_name or h.doc.destination}")
        elif h.doc.kind == "review_dislike":
            hint_bits.append(f"avoid {h.doc.place_name or h.doc.destination}")
        elif h.doc.kind == "trip":
            hint_bits.append(f"visited {h.doc.destination}")
    rewrite_hint = "; ".join(hint_bits)

    return UserMemoryContext(
        profile=profile,
        memories=memories,
        retrieved=top,
        affinity=affinity,
        visit_counts=visit_counts,
        past_tags=past_tags,
        memory_blocks=blocks,
        rewrite_hint=rewrite_hint,
    )


def push_score_for_destination(ctx: UserMemoryContext | None, dest_name: str, dest_text: str = "") -> float:
    """推: personalized affinity from memory RAG (+ place-name soft match)."""
    if ctx is None:
        return 0.0
    score = ctx.affinity.get(dest_name, 0.0)
    blob = (dest_name + " " + dest_text).lower()
    for key, val in ctx.affinity.items():
        if key.startswith("__place__:"):
            place = key.split(":", 1)[1]
            if place and place in blob:
                score += val
    # Cap for stable fusion.
    return max(-0.35, min(0.45, score))


def explore_score_for_destination(
    ctx: UserMemoryContext | None,
    dest_name: str,
    dest_tags: tuple[str, ...] | list[str],
) -> float:
    """广: novelty vs past trips + tag diversity vs historical prefs."""
    if ctx is None or (not ctx.visit_counts and not ctx.past_tags and not ctx.retrieved):
        return 0.5  # neutral for cold start / empty memory
    visits = ctx.visit_counts.get(dest_name, 0)
    novelty = 1.0 / (1.0 + visits)  # 1 if never visited, decays with repeats
    past = set(ctx.past_tags)
    tags = set(dest_tags)
    if not past:
        diversity = 0.5
    elif not tags:
        diversity = 0.4
    else:
        overlap = len(past & tags) / len(past)
        new_ratio = len(tags - past) / len(tags)
        diversity = 0.45 * overlap + 0.55 * new_ratio
    return max(0.0, min(1.0, 0.65 * novelty + 0.35 * diversity))


def fusion_weights(*, has_user: bool, specialty: bool, cold_start: bool) -> tuple[float, float, float]:
    """Return (w_search, w_push, w_explore)."""
    if specialty:
        return (0.70, 0.15, 0.15) if has_user else (0.85, 0.0, 0.15)
    if cold_start or not has_user:
        return (0.75, 0.05, 0.20)
    return (0.50, 0.30, 0.20)
