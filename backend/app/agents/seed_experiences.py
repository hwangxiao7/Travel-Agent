"""Dev seed: plant a few sample experiences near a coordinate for local testing.

Lets you verify the /api/discover flow (e.g. a current-month crayfishing push)
without waiting on the slow public Overpass endpoint. These are illustrative
sample spots — replace with real OSM ingest (`python -m app.agents.ingest --osm`)
for production data.

    python -m app.agents.seed_experiences               # near San Francisco
    python -m app.agents.seed_experiences 37.3382 -121.8863 "San Jose"
"""

from __future__ import annotations

import sys

from app.db import init_db
from app.models.schemas import Place
from app.services.experiences import EXPERIENCE_TYPES
from app.services.trending_store import upsert_spots

_BY_KEY = {e.key: e for e in EXPERIENCE_TYPES}

# (experience_key, name, dlat, dlng) — offsets applied to the origin.
_SAMPLES: list[tuple[str, str, float, float]] = [
    ("fishing", "Lake Merced Crayfishing Spot", -0.05, -0.07),
    ("fishing", "Coyote Creek Fishing Access", -0.06, 0.10),
    ("u_pick", "Webb Ranch U-Pick Berries", -0.14, 0.05),
    ("farmers_market", "Ferry Plaza Farmers Market", 0.02, 0.03),
    ("hot_spring", "Bay Area Hot Springs Retreat", 0.12, -0.06),
    ("botanical_garden", "SF Botanical Garden", -0.01, -0.02),
]


def _place(key: str, name: str, lat: float, lng: float) -> Place:
    exp = _BY_KEY[key]
    return Place(
        name=name,
        category=exp.key,
        kind=exp.kind,  # type: ignore[arg-type]
        lat=lat,
        lng=lng,
        note="",
        recommended=True,
        trending=True,
        experience_tags=list(exp.tags),
        blurb=f"{exp.label} at {name}.",
    )


def main() -> None:
    lat = float(sys.argv[1]) if len(sys.argv) > 1 else 37.7749
    lng = float(sys.argv[2]) if len(sys.argv) > 2 else -122.4194
    dest = sys.argv[3] if len(sys.argv) > 3 else "Seed Area"

    init_db()
    spots = [
        (_place(key, name, lat + dlat, lng + dlng), {"osm"})
        for key, name, dlat, dlng in _SAMPLES
    ]
    created, updated = upsert_spots(dest, spots)
    print(f"Seeded near ({lat},{lng}) as '{dest}': {created} new, {updated} refreshed.")
    for p, _ in spots:
        print(f"  {p.category:16} {p.name}  {p.experience_tags}")


if __name__ == "__main__":
    main()
