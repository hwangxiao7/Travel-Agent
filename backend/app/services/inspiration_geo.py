"""Shared geo / region helpers for inspiration Layer B/C (no merge imports)."""

from __future__ import annotations

from app.config import settings
from app.db import place_key
from app.models.schemas import InspirationPlaceOut


def geo_cell(lat: float, lng: float, *, step: float | None = None) -> str:
    """Coarse grid for geo aggregation (~30–60 km at mid-latitudes when step=0.5)."""
    s = step if step is not None else settings.inspiration_geo_cell_deg
    if not lat and not lng:
        return "geo:unknown"
    return f"geo:{round(lat / s) * s:.1f}:{round(lng / s) * s:.1f}"


def dest_key_for_place(place: InspirationPlaceOut) -> str:
    """Region bucket for catalog — prefer geocode label over raw OCR name."""
    note = (place.note or "").strip()
    if note:
        parts = [p.strip() for p in note.split(",") if p.strip()]
        for part in reversed(parts):
            low = part.lower()
            if low in ("united states", "usa", "us", "canada", "ca"):
                continue
            return place_key(part)
    name = (place.name_en or place.name or "").strip()
    if name:
        return place_key(name)
    if place.lat or place.lng:
        return geo_cell(place.lat, place.lng)
    return "unknown"
