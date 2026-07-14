"""Unified Activity model (design doc §7).

Corpus destinations and live POI hits are different internally, but the doc
wants a single normalized shape carrying `semantic_tags`, `popularity_score`,
and `freshness_score`. This module provides that shape plus adapters, so any
retrieval source maps to the same enriched Activity for ranking/serialization.

We keep the existing `Doc` / `PoiHit` types (no risky rewrite); adapters bridge
them here and enrich via the pluggable `signal_provider`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.signals import signal_provider


@dataclass
class Activity:
    id: str
    name: str
    type: str  # destination | poi
    source: str  # corpus | fly | poi
    lat: float
    lng: float
    region: str = ""
    highlight: str = ""
    travel_mode: str = "drive"  # drive | fly
    semantic_tags: list[str] = field(default_factory=list)
    popularity_score: float = 0.0
    freshness_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "source": self.source,
            "lat": self.lat,
            "lng": self.lng,
            "region": self.region,
            "highlight": self.highlight,
            "travel_mode": self.travel_mode,
            "semantic_tags": self.semantic_tags,
            "popularity_score": round(self.popularity_score, 3),
            "freshness_score": round(self.freshness_score, 3),
        }


def from_doc(doc, *, start_date: str = "") -> Activity:
    """Corpus destination `Doc` → Activity (semantic_tags = curated tags + scenery)."""
    tags = list(doc.tags)
    return Activity(
        id=doc.id,
        name=doc.dest_name,
        type="destination",
        source="fly" if doc.travel_mode == "fly" else "corpus",
        lat=doc.lat,
        lng=doc.lng,
        region=doc.region,
        highlight=doc.highlight,
        travel_mode=doc.travel_mode,
        semantic_tags=tags,
        popularity_score=signal_provider.popularity(text=doc.text, tags=doc.tags),
        freshness_score=signal_provider.freshness(
            text=doc.text, tags=doc.tags, start_date=start_date
        ),
    )


def from_poi(hit, *, start_date: str = "") -> Activity:
    """Live `PoiHit` → Activity. semantic_tags derived from the search phrase."""
    text = f"{hit.name} {hit.highlight} {hit.search_query}"
    tags = [t for t in hit.search_query.lower().split() if len(t) > 2][:4]
    return Activity(
        id=f"poi:{hit.name}",
        name=hit.name,
        type="poi",
        source="poi",
        lat=hit.lat,
        lng=hit.lng,
        region="",
        highlight=hit.highlight,
        travel_mode="drive",
        semantic_tags=tags,
        popularity_score=signal_provider.popularity(text=text, tags=tuple(tags)),
        freshness_score=signal_provider.freshness(
            text=text, tags=tuple(tags), start_date=start_date
        ),
    )
