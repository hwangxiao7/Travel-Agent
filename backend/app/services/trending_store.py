from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from app.config import settings
from app.db import TrendingSpot, get_engine, place_key
from app.models.schemas import Place


def _session():
    get_engine()  # lazily init engine + SessionLocal
    from app.db import SessionLocal  # re-read: set inside get_engine()

    assert SessionLocal is not None
    return SessionLocal()


def _csv_union(existing: str, new: set[str]) -> str:
    parts = {p for p in (existing or "").split(",") if p}
    parts |= new
    return ",".join(sorted(parts))


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
    return [
        Place(
            name=r.name,
            category=r.category or "viral",
            kind=r.kind,  # type: ignore[arg-type]
            lat=r.lat,
            lng=r.lng,
            note="",
            recommended=True,
            trending=True,
        )
        for r in rows[:limit]
    ]


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
