from __future__ import annotations

import httpx

from app.config import settings


async def geocode(query: str, limit: int = 5) -> list[dict]:
    """Return address suggestions as [{label, lat, lng}].

    Uses Mapbox if a token is configured, otherwise falls back to the free
    OpenStreetMap Nominatim service (North America focused).
    """
    query = query.strip()
    if len(query) < 3:
        return []

    if settings.mapbox_token:
        return await _mapbox(query, limit)
    return await _nominatim(query, limit)


async def _mapbox(query: str, limit: int) -> list[dict]:
    url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{httpx.URL(query)}.json"
    params = {
        "access_token": settings.mapbox_token,
        "autocomplete": "true",
        "country": "us,ca",
        "limit": limit,
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        out = []
        for f in data.get("features", []):
            lng, lat = f["center"]
            out.append({"label": f.get("place_name", ""), "lat": lat, "lng": lng})
        return out
    except Exception:
        return []


async def _nominatim(query: str, limit: int) -> list[dict]:
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": limit,
        "countrycodes": "us,ca",
        "addressdetails": 0,
    }
    headers = {"User-Agent": "spontaneous-travel-agent/0.1 (dev)"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return [
            {"label": item["display_name"], "lat": float(item["lat"]), "lng": float(item["lon"])}
            for item in data
        ]
    except Exception:
        return []
