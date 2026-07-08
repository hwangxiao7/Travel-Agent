from __future__ import annotations

from dataclasses import dataclass

from app.services.destinations import DESTINATIONS
from app.services.fly_destinations import FLY_DESTINATIONS

# The RAG corpus is derived from the same curated catalogs that power planning,
# so retrieval always stays in sync with what the app can actually book/plan.
# Each destination becomes one grounding document (overview + tags + highlights).


@dataclass(frozen=True)
class Doc:
    id: str
    text: str
    dest_name: str
    region: str
    lat: float
    lng: float
    tags: tuple[str, ...]
    travel_mode: str  # "drive" | "fly"
    highlight: str = ""
    airport: str = ""


def _dest_text(
    name: str,
    region: str,
    highlight: str,
    tags: tuple[str, ...],
    activities: list[tuple[str, str, str, str]],
) -> str:
    tag_str = ", ".join(t.replace("-", " ") for t in tags)
    acts = "; ".join(f"{place} — {note}" for (_t, place, _d, note) in activities)
    return f"{name} ({region}). {highlight} Good for: {tag_str}. Highlights: {acts}"


def build_corpus() -> list[Doc]:
    docs: list[Doc] = []
    for d in DESTINATIONS:
        tags = tuple(t.value for t in d.tags)
        text = _dest_text(
            d.name, d.region, d.highlight, tags, list(d.day_activities) + list(d.weekend_extra)
        )
        docs.append(
            Doc(
                id=f"drive:{d.name}",
                text=text,
                dest_name=d.name,
                region=d.region,
                lat=d.lat,
                lng=d.lng,
                tags=tags,
                travel_mode="drive",
                highlight=d.highlight,
            )
        )
    for f in FLY_DESTINATIONS:
        tags = tuple(t.value for t in f.tags)
        text = _dest_text(
            f.name, f.region, f.highlight, tags, list(f.day_activities) + list(f.weekend_extra)
        )
        docs.append(
            Doc(
                id=f"fly:{f.name}",
                text=text,
                dest_name=f.name,
                region=f.region,
                lat=f.lat,
                lng=f.lng,
                tags=tags,
                travel_mode="fly",
                highlight=f.highlight,
                airport=f.airport,
            )
        )
    return docs


_BY_NAME: dict[str, Doc] = {d.dest_name: d for d in build_corpus()}


def context_for(name: str) -> str:
    """Grounding text for a destination, used to augment LLM generation."""
    doc = _BY_NAME.get(name)
    return doc.text if doc else ""
