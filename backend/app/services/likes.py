"""Batch like sync → taste snippets + feedback for RAG personalization.

Clients buffer double-tap likes locally and POST a batch to save IO.
Unlike removes the pending signal (and any stored snippet with the same source key).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import FeedbackEvent, TasteSnippet, User, place_key
from app.services.persona import get_or_build_persona
from app.services.taste_profile import invalidate, record_snippet


def _source(kind: str, key: str) -> str:
    return f"like:{kind}:{place_key(key)}"


def _snippet_text(
    *,
    kind: str,
    name: str,
    tags: list[str],
    blurb: str,
    origin_label: str,
    persona_title: str,
    persona_blurb: str,
) -> str:
    tag_s = ", ".join(tags[:8]) if tags else ""
    geo = f" near {origin_label}" if origin_label else ""
    persona = ""
    if persona_title:
        persona = f" Traveler persona: {persona_title}."
        if persona_blurb:
            persona += f" {persona_blurb[:160]}"
    body = blurb.strip()[:200]
    kind_label = "activity idea" if kind == "activity" else "trip destination"
    parts = [
        f"User liked {kind_label}: {name}{geo}.",
        f"Tags: {tag_s}." if tag_s else "",
        body,
        persona,
    ]
    return " ".join(p for p in parts if p).strip()


def apply_like_batch(
    db: Session,
    user: User,
    *,
    items: list[dict],
    origin_label: str = "",
    origin_lat: float = 0.0,
    origin_lng: float = 0.0,
) -> dict:
    """Apply like/unlike ops. Returns counts."""
    persona = get_or_build_persona(db, user)
    persona_title = getattr(persona, "title", "") or ""
    persona_blurb = getattr(persona, "blurb", "") or ""

    liked = 0
    unliked = 0
    for raw in items:
        op = (raw.get("op") or "").strip().lower()
        kind = (raw.get("kind") or "activity").strip().lower()
        if kind not in {"activity", "destination"}:
            kind = "activity"
        key = (raw.get("key") or raw.get("name") or "").strip()
        name = (raw.get("name") or key).strip()
        if not key or op not in {"like", "unlike"}:
            continue
        src = _source(kind, key)
        tags = [t for t in (raw.get("tags") or []) if isinstance(t, str)][:12]
        blurb = str(raw.get("blurb") or raw.get("highlight") or raw.get("reason") or "")

        if op == "unlike":
            rows = db.scalars(
                select(TasteSnippet).where(
                    TasteSnippet.user_id == user.id, TasteSnippet.source == src
                )
            ).all()
            for row in rows:
                db.delete(row)
            # Drop matching like feedback events for this place/dest.
            evs = db.scalars(
                select(FeedbackEvent).where(
                    FeedbackEvent.user_id == user.id,
                    FeedbackEvent.event_type == "like",
                    FeedbackEvent.place_key == place_key(name),
                )
            ).all()
            for e in evs:
                db.delete(e)
            unliked += 1
            continue

        text = _snippet_text(
            kind=kind,
            name=name,
            tags=tags,
            blurb=blurb,
            origin_label=origin_label,
            persona_title=persona_title,
            persona_blurb=persona_blurb,
        )
        # Replace prior snippet for this key (idempotent like).
        existing = db.scalars(
            select(TasteSnippet).where(
                TasteSnippet.user_id == user.id, TasteSnippet.source == src
            )
        ).all()
        for row in existing:
            db.delete(row)
        record_snippet(db, user, text, source=src, weight=1.35, polarity=1.0)
        db.add(
            FeedbackEvent(
                user_id=user.id,
                event_type="like",
                place_key=place_key(name),
                place_name=name[:200],
                destination=name[:200] if kind == "destination" else "",
                value=1.0,
            )
        )
        liked += 1

    db.commit()
    invalidate(user.id)
    return {"liked": liked, "unliked": unliked, "origin": origin_label or f"{origin_lat},{origin_lng}"}
