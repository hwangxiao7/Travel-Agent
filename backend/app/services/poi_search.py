"""Secondary search path: nearby POI lookup when curated corpus has no match.

This is NOT "fallback to parks". When free-text focus misses the catalog,
we search real places near the origin (Nominatim), with the query rewritten
by LLM into an English place-search phrase — no synonym / alias tables.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.services.geo import estimate_drive_hours, format_duration, haversine_miles
from app.services.query_understanding import TravelIntent, llm_activity_phrase


@dataclass
class PoiHit:
    name: str
    lat: float
    lng: float
    label: str
    drive_hours: float
    drive_time: str
    highlight: str
    score: float
    search_query: str = ""

    def to_candidate_dict(self) -> dict:
        from app.services.signals import signal_provider

        blob = f"{self.name} {self.highlight} {self.search_query}"
        tags = [t for t in self.search_query.lower().split() if len(t) > 2][:4]
        return {
            "name": self.name,
            "lat": self.lat,
            "lng": self.lng,
            "drive_time": self.drive_time,
            "drive_hours": round(self.drive_hours, 2),
            "score": round(self.score, 3),
            "highlight": self.highlight,
            "final_score": round(self.score, 3),
            # Unified Activity fields (doc §7).
            "activity_type": "poi",
            "source": "poi",
            "semantic_tags": tags,
            "popularity_score": round(signal_provider.popularity(text=blob, tags=tuple(tags)), 3),
            "freshness_score": round(signal_provider.freshness(text=blob, tags=tuple(tags)), 3),
        }


def _query_variants(phrase: str) -> list[str]:
    """Short OSM-friendly variants from an LLM activity phrase (no synonym table)."""
    p = " ".join(phrase.strip().split())
    if not p:
        return []
    out: list[str] = []
    # Drop trailing filler nouns that hurt Nominatim ("spot", "place", "venue").
    trimmed = p
    for filler in (" spot", " place", " venue", " location", " nearby", " area", " site"):
        if trimmed.lower().endswith(filler):
            trimmed = trimmed[: -len(filler)].strip()
    for candidate in (trimmed, p):
        if candidate and candidate not in out:
            out.append(candidate)
    # Prefer shorter first for OSM.
    return sorted(out, key=len)


async def _place_search_queries(query: str) -> list[str]:
    """LLM → English activity phrase(s) for Nominatim. No alias tables."""
    phrase = await llm_activity_phrase(query)
    if phrase:
        return _query_variants(phrase)
    q = query.strip()
    if q and all(ord(c) < 128 for c in q):
        return _query_variants(q[:40])
    return []


async def _nominatim_search(
    client: httpx.AsyncClient,
    *,
    search_q: str,
    viewbox: str,
    limit: int,
) -> list:
    headers = {"User-Agent": "spontaneous-travel-agent/0.1 (dev)"}
    base_params = {
        "q": search_q,
        "format": "jsonv2",
        "limit": max(limit * 2, 10),
        "countrycodes": "us,ca",
        "addressdetails": 0,
    }
    resp = await client.get(
        "https://nominatim.openstreetmap.org/search",
        params={**base_params, "viewbox": viewbox, "bounded": 1},
        headers=headers,
    )
    resp.raise_for_status()
    data = resp.json()
    if data:
        return data
    resp = await client.get(
        "https://nominatim.openstreetmap.org/search",
        params=base_params,
        headers=headers,
    )
    resp.raise_for_status()
    return resp.json()


async def search_nearby_pois(
    *,
    query: str,
    intent: TravelIntent,
    origin_lat: float,
    origin_lng: float,
    max_drive_hours: float = 3.0,
    limit: int = 8,
) -> list[PoiHit]:
    """Search real nearby places for the free-text activity (secondary path)."""
    candidates = await _place_search_queries(query)
    if not candidates:
        return []

    deg = max(0.35, min(2.5, max_drive_hours * 0.65))
    viewbox = f"{origin_lng - deg},{origin_lat + deg},{origin_lng + deg},{origin_lat - deg}"

    data: list = []
    search_q = candidates[0]
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            for q in candidates:
                data = await _nominatim_search(
                    client, search_q=q, viewbox=viewbox, limit=limit
                )
                if data:
                    search_q = q
                    break
    except Exception:
        data = []

    hits: list[PoiHit] = []
    seen: set[str] = set()
    for item in data:
        try:
            lat = float(item["lat"])
            lng = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        hours = estimate_drive_hours(haversine_miles(origin_lat, origin_lng, lat, lng))
        if hours > max_drive_hours + 0.75:
            continue
        display = item.get("display_name") or ""
        name = (item.get("name") or (display.split(",")[0] if display else "")).strip()
        if len(name) < 2:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        locality = ""
        if "," in display:
            parts = [p.strip() for p in display.split(",")]
            locality = parts[1] if len(parts) > 1 else ""
        score = max(0.05, 1.0 - hours / max(max_drive_hours, 0.5))
        hits.append(
            PoiHit(
                name=name,
                lat=lat,
                lng=lng,
                label=display,
                drive_hours=hours,
                drive_time=format_duration(hours),
                highlight=(
                    f"Found via place search for “{search_q}”"
                    + (f" · {locality}" if locality else "")
                    + "."
                ),
                score=score,
                search_query=search_q,
            )
        )

    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]
