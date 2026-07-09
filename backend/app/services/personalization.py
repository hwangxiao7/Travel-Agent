from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import PlaceReview, Trip, User, place_key


@dataclass
class UserProfile:
    display_name: str = ""
    past_destinations: list[str] = field(default_factory=list)
    liked_places: list[str] = field(default_factory=list)
    disliked_places: list[str] = field(default_factory=list)
    liked_destinations: list[str] = field(default_factory=list)
    disliked_destinations: list[str] = field(default_factory=list)
    activity_preferences: list[str] = field(default_factory=list)
    travel_pace: str | None = None
    profile_text: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def build_user_profile(db: Session, user: User) -> UserProfile:
    """Structured profile from trips + reviews for personalized RAG."""
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

    # Infer activity prefs from destination names / place notes (lightweight).
    activity_prefs: list[str] = []
    blob = " ".join(
        [t.destination for t in trips]
        + [r.place_name + " " + r.comment for r in liked]
        + places_visited
    ).lower()
    for needle, label in (
        ("hike", "hiking"),
        ("trail", "hiking"),
        ("park", "national-park"),
        ("beach", "beach"),
        ("coast", "beach"),
        ("forest", "forest"),
        ("redwood", "forest"),
        ("city", "city-walk"),
    ):
        if needle in blob and label not in activity_prefs:
            activity_prefs.append(label)

    pace = None
    easy_hits = sum(1 for r in liked if any(w in (r.comment or "").lower() for w in ("easy", "relax", "轻松", "休闲")))
    hard_hits = sum(1 for r in liked if any(w in (r.comment or "").lower() for w in ("hard", "steep", "challenging", "累")))
    if easy_hits > hard_hits and easy_hits > 0:
        pace = "easy"
    elif hard_hits > easy_hits and hard_hits > 0:
        pace = "strenuous"

    profile = UserProfile(
        display_name=user.display_name or user.email,
        past_destinations=[d for d, _ in dest_counts.most_common(8)],
        liked_places=[r.place_name for r in liked[:8]],
        disliked_places=[r.place_name for r in disliked[:5]],
        liked_destinations=list(dict.fromkeys(r.destination for r in liked if r.destination))[:8],
        disliked_destinations=list(dict.fromkeys(r.destination for r in disliked if r.destination))[:5],
        activity_preferences=activity_prefs,
        travel_pace=pace,
    )
    parts = [
        f"Traveler profile for {profile.display_name}.",
        f"Past destinations: {', '.join(f'{d} ({n}x)' for d, n in dest_counts.most_common(8)) or 'none yet'}.",
        f"Places visited: {', '.join(list(dict.fromkeys(places_visited))[:12]) or 'none yet'}.",
        f"Highly rated places: {', '.join(f'{r.place_name} ({r.rating}/5)' for r in liked[:8]) or 'none yet'}.",
        f"Lower rated places: {', '.join(f'{r.place_name} ({r.rating}/5)' for r in disliked[:5]) or 'none'}.",
    ]
    if activity_prefs:
        parts.append("Preferred activities: " + ", ".join(activity_prefs) + ".")
    if pace:
        parts.append(f"Preferred pace: {pace}.")
    if liked:
        parts.append(
            "Prefer destinations similar to highly rated places; avoid repeating low-rated ones when alternatives exist."
        )
    profile.profile_text = " ".join(parts)
    return profile


def rebuild_profile_text(db: Session, user: User) -> str:
    return build_user_profile(db, user).profile_text


def personalization_boost(db: Session, user: User | None, dest_name: str) -> float:
    """Score delta for retrieval ranking based on this user's history."""
    if user is None:
        return 0.0
    boost = 0.0
    liked = db.scalars(
        select(PlaceReview).where(
            PlaceReview.user_id == user.id,
            PlaceReview.destination == dest_name,
            PlaceReview.rating >= 4,
        )
    ).all()
    boost += 0.08 * min(len(liked), 3)

    trip_n = db.scalar(
        select(func.count()).select_from(Trip).where(Trip.user_id == user.id, Trip.destination == dest_name)
    ) or 0
    if trip_n:
        boost += 0.03

    low = db.scalars(
        select(PlaceReview).where(
            PlaceReview.user_id == user.id,
            PlaceReview.destination == dest_name,
            PlaceReview.rating <= 2,
        )
    ).all()
    boost -= 0.1 * min(len(low), 3)

    # Soft boost if destination name overlaps liked place names
    liked_places = db.scalars(
        select(PlaceReview).where(PlaceReview.user_id == user.id, PlaceReview.rating >= 4)
    ).all()
    dest_l = dest_name.lower()
    if any(p.place_name.lower() in dest_l or dest_l.split()[0] in p.place_name.lower() for p in liked_places):
        boost += 0.04

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
