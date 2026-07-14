"""Background ingestion: distill social posts into verified trending spots.

This is the "refinery": raw social posts (ore) are fanned in from every enabled
provider, the LLM extracts real place names (facts), each name is verified +
geocoded against OSM (authoritative source / legal firewall), duplicates are
merged and cross-validated across platforms, and only the resulting facts —
plus provenance and freshness timestamps — are persisted via trending_store.

Run per-destination on a schedule (cron / task runner), not per user request:

    python -m app.agents.ingest            # ingest all catalog destinations
    python -m app.agents.ingest --drive    # drive-to catalog only
    python -m app.agents.ingest --limit 5  # first N (smoke test)
"""

from __future__ import annotations

import argparse
import asyncio

from app.db import init_db
from app.services.destinations import DESTINATIONS
from app.services.experiences import fetch_osm_experiences
from app.services.fly_destinations import FLY_DESTINATIONS
from app.services.geo import haversine_miles
from app.services.social import collect_social_signals, enabled_providers, enrich_experiences
from app.services.trending_store import upsert_spots
from app.config import settings


async def ingest_destination(name: str, lat: float, lng: float, language: str = "en") -> dict:
    """Distill + persist trending spots for a single destination."""
    located, guides = await collect_social_signals(name, lat, lng, language)
    # Radius guard: keep only spots genuinely near this destination.
    radius = settings.trending_radius_miles
    near = [
        (place, sources)
        for place, sources in located
        if haversine_miles(lat, lng, place.lat, place.lng) <= radius
    ]
    # Tag each kept spot with experience attributes for persona matching.
    await enrich_experiences(
        [place for place, _ in near], "\n".join(g.title for g in guides), language
    )
    created, updated = upsert_spots(name, near)
    return {
        "destination": name,
        "guides_seen": len(guides),
        "spots_located": len(located),
        "spots_kept": len(near),
        "created": created,
        "updated": updated,
    }


async def ingest_osm_destination(name: str, lat: float, lng: float) -> dict:
    """Populate experiences from OpenStreetMap (no social, no keys needed)."""
    radius_m = int(settings.trending_radius_miles * 1609)
    places = await fetch_osm_experiences(lat, lng, radius_m=radius_m)
    located = [(p, {"osm"}) for p in places]
    created, updated = upsert_spots(name, located)
    return {
        "destination": name,
        "osm_spots": len(places),
        "created": created,
        "updated": updated,
    }


async def ingest_osm_all(*, drive_only: bool = False, fly_only: bool = False, limit: int = 0) -> list[dict]:
    """Sequentially ingest OSM experiences for catalog destinations."""
    import asyncio as _asyncio

    init_db()
    targets: list[tuple[str, float, float]] = []
    if not fly_only:
        targets += [(d.name, d.lat, d.lng) for d in DESTINATIONS]
    if not drive_only:
        targets += [(f.name, f.lat, f.lng) for f in FLY_DESTINATIONS]
    if limit > 0:
        targets = targets[:limit]

    reports: list[dict] = []
    for i, (name, lat, lng) in enumerate(targets, 1):
        try:
            report = await ingest_osm_destination(name, lat, lng)
        except Exception as exc:
            report = {"destination": name, "error": str(exc)}
        reports.append(report)
        print(f"[osm {i}/{len(targets)}] {report}")
        if i < len(targets):
            await _asyncio.sleep(1.5)  # be polite to the shared Overpass endpoint
    return reports


async def ingest_all(*, drive_only: bool = False, fly_only: bool = False, limit: int = 0) -> list[dict]:
    """Sequentially ingest catalog destinations (polite to shared OSM endpoints)."""
    init_db()
    providers = enabled_providers()
    if not providers:
        print("No social providers configured (set RAPIDAPI_KEY + a *_HOST). Nothing to ingest.")
        return []
    print(f"Enabled providers: {', '.join(p.name for p in providers)}")

    targets: list[tuple[str, float, float]] = []
    if not fly_only:
        targets += [(d.name, d.lat, d.lng) for d in DESTINATIONS]
    if not drive_only:
        targets += [(f.name, f.lat, f.lng) for f in FLY_DESTINATIONS]
    if limit > 0:
        targets = targets[:limit]

    reports: list[dict] = []
    for i, (name, lat, lng) in enumerate(targets, 1):
        try:
            report = await ingest_destination(name, lat, lng)
        except Exception as exc:  # keep going; one bad dest shouldn't stop the run
            report = {"destination": name, "error": str(exc)}
        reports.append(report)
        print(f"[{i}/{len(targets)}] {report}")
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest experiences/trending spots.")
    parser.add_argument("--drive", action="store_true", help="drive-to catalog only")
    parser.add_argument("--fly", action="store_true", help="fly-to catalog only")
    parser.add_argument("--limit", type=int, default=0, help="only first N destinations")
    parser.add_argument(
        "--osm", action="store_true",
        help="ingest experiences from OpenStreetMap (no social, no keys)",
    )
    args = parser.parse_args()
    runner = ingest_osm_all if args.osm else ingest_all
    reports = asyncio.run(runner(drive_only=args.drive, fly_only=args.fly, limit=args.limit))
    created = sum(r.get("created", 0) for r in reports)
    updated = sum(r.get("updated", 0) for r in reports)
    src = "OSM experiences" if args.osm else "social"
    print(f"\nDone ({src}). {len(reports)} destinations, {created} new, {updated} refreshed.")


if __name__ == "__main__":
    main()
