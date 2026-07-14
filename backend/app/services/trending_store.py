from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.config import settings
from app.db import TrendingSpot, get_engine, place_key
from app.models.schemas import Place
from app.services.geo import haversine_miles


def _session():
    get_engine()  # lazily init engine + SessionLocal
    from app.db import SessionLocal  # re-read: set inside get_engine()

    assert SessionLocal is not None
    return SessionLocal()


def _csv_union(existing: str, new: set[str]) -> str:
    parts = {p for p in (existing or "").split(",") if p}
    parts |= new
    return ",".join(sorted(parts))


def _tags_list(csv: str) -> list[str]:
    return [t for t in (csv or "").split(",") if t]


def upsert_spots(
    dest_name: str, spots: list[tuple[Place, set[str]]]
) -> tuple[int, int]:
    """Persist distilled spots for a destination. Facts + provenance only.

    Returns (created, updated). Re-seeing a spot merges its platform set,
    bumps mention_count, and refreshes last_seen (freshness)."""
    if not spots:
        return 0, 0
    dkey = place_key(dest_name)
    now = datetime.utcnow()
    created = updated = 0
    session = _session()
    try:
        for place, sources in spots:
            pkey = place_key(place.name)
            row = session.execute(
                select(TrendingSpot).where(
                    TrendingSpot.dest_key == dkey, TrendingSpot.place_key == pkey
                )
            ).scalar_one_or_none()
            tags_csv = ",".join(place.experience_tags) if place.experience_tags else ""
            if row is None:
                session.add(
                    TrendingSpot(
                        dest_key=dkey,
                        dest_name=dest_name,
                        place_key=pkey,
                        name=place.name,
                        category=place.category or "viral",
                        kind=place.kind,
                        lat=place.lat,
                        lng=place.lng,
                        platforms=",".join(sorted(sources)),
                        mention_count=1,
                        experience_tags=tags_csv,
                        blurb=place.blurb or "",
                        first_seen=now,
                        last_seen=now,
                    )
                )
                created += 1
            else:
                row.platforms = _csv_union(row.platforms, sources)
                row.mention_count += 1
                row.last_seen = now
                # Keep coords fresh (OSM may refine); harmless if identical.
                row.lat, row.lng, row.kind = place.lat, place.lng, place.kind
                # Merge experience tags; keep the latest non-empty blurb.
                if place.experience_tags:
                    row.experience_tags = _csv_union(row.experience_tags, set(place.experience_tags))
                if place.blurb:
                    row.blurb = place.blurb
                updated += 1
        session.commit()
    finally:
        session.close()
    return created, updated


def _confidence(row: TrendingSpot) -> float:
    """Cross-validated trust: more platforms + more mentions = higher."""
    n_platforms = len([p for p in (row.platforms or "").split(",") if p])
    return n_platforms * 2.0 + min(row.mention_count, 5) * 0.5


def get_trending_places(dest_name: str, limit: int = 8) -> list[Place]:
    """Serve distilled trending spots for a destination (fresh ones only)."""
    dkey = place_key(dest_name)
    cutoff = datetime.utcnow() - timedelta(days=settings.trending_stale_days)
    session = _session()
    try:
        rows = list(
            session.execute(
                select(TrendingSpot).where(
                    TrendingSpot.dest_key == dkey, TrendingSpot.last_seen >= cutoff
                )
            ).scalars()
        )
    finally:
        session.close()
    rows.sort(key=lambda r: (_confidence(r), r.last_seen), reverse=True)
    return [_row_to_place(r) for r in rows[:limit]]


def _row_to_place(r: TrendingSpot) -> Place:
    return Place(
        name=r.name,
        category=r.category or "viral",
        kind=r.kind,  # type: ignore[arg-type]
        lat=r.lat,
        lng=r.lng,
        note="",
        recommended=True,
        trending=True,
        experience_tags=_tags_list(r.experience_tags),
        blurb=r.blurb or "",
    )


def get_spots_near(lat: float, lng: float, radius_miles: float, limit: int = 60) -> list[dict]:
    """Fresh trending spots near a coordinate, across ALL destinations.

    Returns lightweight dicts (place + provenance + freshness) for the discovery
    engine to rank by persona match. Spatial filter is a haversine scan — fine at
    catalog scale; swap for PostGIS/geohash when the table grows large."""
    cutoff = datetime.utcnow() - timedelta(days=settings.trending_stale_days)
    now = datetime.utcnow()
    session = _session()
    try:
        rows = list(
            session.execute(
                select(TrendingSpot).where(TrendingSpot.last_seen >= cutoff)
            ).scalars()
        )
    finally:
        session.close()
    out: list[dict] = []
    for r in rows:
        miles = haversine_miles(lat, lng, r.lat, r.lng)
        if miles > radius_miles:
            continue
        out.append(
            {
                "place": _row_to_place(r),
                "platforms": _tags_list(r.platforms),
                "distance_miles": round(miles, 1),
                "freshness_days": max(0, (now - r.last_seen).days),
                "confidence": _confidence(r),
            }
        )
    out.sort(key=lambda d: d["distance_miles"])
    return out[:limit]


def has_trending(dest_name: str) -> bool:
    dkey = place_key(dest_name)
    cutoff = datetime.utcnow() - timedelta(days=settings.trending_stale_days)
    session = _session()
    try:
        row = session.execute(
            select(TrendingSpot.id).where(
                TrendingSpot.dest_key == dkey, TrendingSpot.last_seen >= cutoff
            )
        ).first()
        return row is not None
    finally:
        session.close()
