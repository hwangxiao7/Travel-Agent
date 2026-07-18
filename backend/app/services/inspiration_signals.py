"""Layer B/C signals from private screenshot inspiration (opt-in crowd).

After a user saves inspiration (Layer A), optionally contribute:
- InteractionEvent rows → nightly CrowdSignal rollup (persona × activity/place)
- Canonical place nominations → k-anonymous aggregate → verified TrendingSpot

Multiple screenshots naming the same POI merge into one aggregate row.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import InspirationPlaceNomination, User, place_key
from app.models.schemas import InspirationPlaceOut, Place
from app.services.crowd import top_items_for_persona
from app.services.inspiration_geo import dest_key_for_place, geo_cell
from app.services.inspiration_place_merge import resolve_or_create_agg
from app.services.interaction_log import intent_for_inspiration, log_events
from app.services.persona import get_or_build_persona
from app.services.trending_store import upsert_spots

logger = logging.getLogger("travel_agent")

_NOMINATION_PLATFORM = "user_nomination"


def activity_item_key(title: str) -> str:
    return f"insp-act:{place_key(title)}"[:220]


def place_item_key(canonical_key: str) -> str:
    return f"insp-place:{canonical_key}"[:220]


def publish_inspiration_signals(
    db: Session,
    user: User,
    ext: Any,
    places: list[InspirationPlaceOut],
    *,
    origin_lat: float = 0.0,
    origin_lng: float = 0.0,
) -> dict:
    """Best-effort Layer B/C publish. Honors crowd_opt_out."""
    if getattr(user, "crowd_opt_out", False):
        return {"skipped": "crowd_opt_out"}

    persona = get_or_build_persona(db, user)
    intent = intent_for_inspiration(ext.tags, ext.activity_title)
    events: list[dict] = []

    act_key = activity_item_key(ext.activity_title)
    events.append(
        {
            "stage": "saved",
            "surface": "inspiration",
            "intent_key": intent,
            "item_key": act_key,
            "item_name": ext.activity_title,
            "item_kind": "inspiration",
        }
    )

    nominations = 0
    merged = 0
    promoted = 0
    k = settings.inspiration_nomination_k

    for p in places:
        pname = (p.name or p.name_en or "").strip()
        if not pname:
            continue
        note = (p.note or "").strip()
        dest_display = note.split(",")[0].strip() if note else pname
        cell = geo_cell(p.lat, p.lng) if (p.lat or p.lng) else geo_cell(origin_lat, origin_lng)

        agg, created = resolve_or_create_agg(
            db,
            place=p,
            dest_display=dest_display,
            activity_key=act_key,
            tags=list(ext.tags or []),
            summary=(ext.summary or ""),
            activity_title=(ext.activity_title or ""),
        )
        if not created:
            merged += 1

        events.append(
            {
                "stage": "saved",
                "surface": "inspiration",
                "intent_key": intent,
                "item_key": place_item_key(agg.canonical_key),
                "item_name": agg.place_name or pname,
                "item_kind": "place",
            }
        )

        existing = db.scalar(
            select(InspirationPlaceNomination).where(
                InspirationPlaceNomination.user_id == user.id,
                InspirationPlaceNomination.canonical_key == agg.canonical_key,
            )
        )
        if existing:
            continue

        db.add(
            InspirationPlaceNomination(
                user_id=user.id,
                canonical_key=agg.canonical_key,
                dest_key=agg.dest_key,
                dest_name=dest_display[:200],
                place_key=place_key(p.name_en or pname),
                place_name=pname,
                lat=float(p.lat or 0),
                lng=float(p.lng or 0),
                geo_cell=cell,
                activity_key=act_key,
                tags_csv=",".join(ext.tags[:6]),
            )
        )
        agg.n_users += 1
        nominations += 1

        db.flush()
        if agg.n_users >= k and agg.lat and agg.lng and not agg.promoted:
            dest_for_catalog = agg.dest_name if not agg.dest_key.startswith("geo:") else agg.place_name
            tags = [t for t in (agg.tags_csv or "").split(",") if t]
            place = Place(
                name=agg.place_name,
                category="experience",
                kind="fun",
                lat=agg.lat,
                lng=agg.lng,
                trending=True,
                experience_tags=tags,
                blurb=agg.blurb or "",
            )
            upsert_spots(dest_for_catalog, [(place, {_NOMINATION_PLATFORM})])
            agg.promoted = 1
            promoted += 1

    log_events(user, events, persona=persona)
    return {
        "events": len(events),
        "nominations": nominations,
        "merged_into_existing": merged,
        "promoted": promoted,
    }


def crowd_picks_for_user(
    db: Session,
    user: User,
    *,
    lat: float = 0.0,
    lng: float = 0.0,
    radius_deg: float = 1.0,
    limit: int = 8,
) -> list[dict]:
    """Layer B picks: persona crowd signals + k-anonymous canonical places."""
    from app.db import InspirationPlaceNominationAgg

    k = settings.inspiration_nomination_k
    persona = get_or_build_persona(db, user)
    out: list[dict] = []
    seen: set[str] = set()

    for row in top_items_for_persona(db, persona, kind="inspiration", limit=limit, k=k):
        key = row["item_key"]
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "item_key": key,
                "name": row["item_name"],
                "kind": row["item_kind"] or "inspiration",
                "affinity": row["affinity"],
                "n_users": row["n_users"],
                "lat": 0.0,
                "lng": 0.0,
                "verified": False,
                "blurb": "",
            }
        )

    for row in top_items_for_persona(db, persona, kind="place", limit=limit, k=k):
        key = row["item_key"]
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "item_key": key,
                "name": row["item_name"],
                "kind": "place",
                "affinity": row["affinity"],
                "n_users": row["n_users"],
                "lat": 0.0,
                "lng": 0.0,
                "verified": False,
                "blurb": "",
            }
        )

    if lat or lng:
        cell = geo_cell(lat, lng)
        rows = db.scalars(
            select(InspirationPlaceNominationAgg).where(
                InspirationPlaceNominationAgg.n_users >= k,
            )
        ).all()
        geo_rows: list[InspirationPlaceNominationAgg] = []
        for r in rows:
            if r.geo_cell == cell:
                geo_rows.append(r)
            elif r.lat and r.lng and abs(r.lat - lat) <= radius_deg and abs(r.lng - lng) <= radius_deg:
                geo_rows.append(r)
        geo_rows.sort(key=lambda r: (-r.n_users, -r.n_mentions, r.place_name))
        for r in geo_rows:
            key = place_item_key(r.canonical_key)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "item_key": key,
                    "name": r.place_name,
                    "kind": "place",
                    "affinity": min(1.0, 0.5 + 0.1 * r.n_users),
                    "n_users": r.n_users,
                    "n_mentions": r.n_mentions,
                    "lat": r.lat,
                    "lng": r.lng,
                    "verified": bool(r.promoted),
                    "blurb": r.blurb or "",
                }
            )
            if len(out) >= limit:
                break

    return out[:limit]
