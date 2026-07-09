from __future__ import annotations

import json
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import PlaceReview, Trip, User, place_key


def rebuild_profile_text(db: Session, user: User) -> str:
    """Build a short natural-language profile used to personalize RAG."""
    trips = db.scalars(select(Trip).where(Trip.user_id == user.id).order_by(Trip.created_at.desc())).all()
    reviews = db.scalars(
        select(PlaceReview).where(PlaceReview.user_id == user.id).order_by(PlaceReview.updated_at.desc())
    ).all()

    dest_counts = Counter(t.destination for t in trips)
    liked = [r for r in reviews if r.rating >= 4]
    disliked = [r for r in reviews if r.rating <= 2]
    places_visited: list[str] = []
    for t in trips:
        try:
            places_visited.extend(json.loads(t.places_json or "[]"))
        except json.JSONDecodeError:
            pass

    parts = [
        f"Traveler profile for {user.display_name or user.email}.",
        f"Past destinations: {', '.join(f'{d} ({n}x)' for d, n in dest_counts.most_common(8)) or 'none yet'}.",
        f"Places visited: {', '.join(list(dict.fromkeys(places_visited))[:12]) or 'none yet'}.",
        f"Highly rated places: {', '.join(f'{r.place_name} ({r.rating}/5)' for r in liked[:8]) or 'none yet'}.",
        f"Lower rated places: {', '.join(f'{r.place_name} ({r.rating}/5)' for r in disliked[:5]) or 'none'}.",
    ]
    if liked:
        parts.append(
            "Prefer destinations similar to highly rated places; avoid repeating low-rated ones when alternatives exist."
        )
    return " ".join(parts)


def personalization_boost(db: Session, user: User | None, dest_name: str) -> float:
    """Small score delta for retrieval ranking based on this user's history."""
    if user is None:
        return 0.0
    boost = 0.0
    # Liked places at/near this destination
    liked = db.scalars(
        select(PlaceReview).where(
            PlaceReview.user_id == user.id,
            PlaceReview.destination == dest_name,
            PlaceReview.rating >= 4,
        )
    ).all()
    boost += 0.08 * min(len(liked), 3)

    # Past trips to same destination (mild familiarity boost, not too strong)
    trip_n = db.scalar(
        select(func.count()).select_from(Trip).where(Trip.user_id == user.id, Trip.destination == dest_name)
    ) or 0
    if trip_n:
        boost += 0.03

    # Penalize destinations where user left mostly low ratings
    low = db.scalars(
        select(PlaceReview).where(
            PlaceReview.user_id == user.id,
            PlaceReview.destination == dest_name,
            PlaceReview.rating <= 2,
        )
    ).all()
    boost -= 0.1 * min(len(low), 3)
    return boost


def public_reviews_for_place(db: Session, name: str, limit: int = 50) -> tuple[list[PlaceReview], float, int]:
    key = place_key(name)
    rows = db.scalars(
        select(PlaceReview)
        .where(PlaceReview.place_key == key)
        .order_by(PlaceReview.updated_at.desc())
        .limit(limit)
    ).all()
    if not rows:
        return [], 0.0, 0
    avg = sum(r.rating for r in rows) / len(rows)
    return list(rows), round(avg, 2), len(rows)
