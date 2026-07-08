from __future__ import annotations

import httpx

from app.models.schemas import Place
from app.services.geo import haversine_miles

# Free, no-key POI source (same OpenStreetMap ecosystem as geocoding + Leaflet tiles).
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Overpass rejects requests without a User-Agent (HTTP 406), same as Nominatim.
_HEADERS = {"User-Agent": "spontaneous-travel-agent/0.1 (dev)"}

# amenity=* values treated as "food"
FOOD_AMENITIES = {"restaurant", "cafe", "fast_food", "bar", "pub", "ice_cream", "food_court"}
# tourism=* / leisure=* values treated as "fun"
FUN_TOURISM = {"attraction", "viewpoint", "museum", "artwork", "theme_park", "zoo", "aquarium", "gallery"}
FUN_LEISURE = {"park", "nature_reserve", "garden"}

# Map raw OSM tag values -> stable machine category keys the frontend can localize.
_CATEGORY = {
    "restaurant": "restaurant",
    "cafe": "cafe",
    "fast_food": "fast_food",
    "bar": "bar",
    "pub": "bar",
    "ice_cream": "ice_cream",
    "food_court": "restaurant",
    "attraction": "attraction",
    "viewpoint": "viewpoint",
    "museum": "museum",
    "artwork": "artwork",
    "theme_park": "theme_park",
    "zoo": "zoo",
    "aquarium": "aquarium",
    "gallery": "gallery",
    "park": "park",
    "nature_reserve": "park",
    "garden": "park",
}


def _build_query(lat: float, lng: float, radius_m: int, cap: int) -> str:
    food = "|".join(sorted(FOOD_AMENITIES))
    tourism = "|".join(sorted(FUN_TOURISM))
    leisure = "|".join(sorted(FUN_LEISURE))
    return (
        f"[out:json][timeout:15];"
        f"("
        f'node["amenity"~"^({food})$"]["name"](around:{radius_m},{lat},{lng});'
        f'node["tourism"~"^({tourism})$"]["name"](around:{radius_m},{lat},{lng});'
        f'node["leisure"~"^({leisure})$"]["name"](around:{radius_m},{lat},{lng});'
        f");"
        f"out center {cap};"
    )


def _to_place(el: dict) -> Place | None:
    tags = el.get("tags", {})
    name = tags.get("name")
    if not name:
        return None
    lat = el.get("lat") or el.get("center", {}).get("lat")
    lng = el.get("lon") or el.get("center", {}).get("lon")
    if lat is None or lng is None:
        return None

    amenity = tags.get("amenity")
    if amenity in FOOD_AMENITIES:
        kind = "food"
        raw = amenity
        note = tags.get("cuisine", "").replace("_", " ").replace(";", ", ")
    else:
        kind = "fun"
        raw = tags.get("tourism") or tags.get("leisure") or "attraction"
        note = tags.get("description", "")

    recommended = "wikidata" in tags or "wikipedia" in tags
    return Place(
        name=name,
        category=_CATEGORY.get(raw, raw),
        kind=kind,  # type: ignore[arg-type]
        lat=float(lat),
        lng=float(lng),
        note=note,
        recommended=recommended,
    )


async def fetch_nearby_places(
    lat: float,
    lng: float,
    radius_m: int = 12000,
    limit_each: int = 6,
) -> tuple[list[Place], list[Place]]:
    """Return (food, fun) POIs near a destination via OpenStreetMap Overpass.

    Best-effort: any failure returns empty lists so planning never blocks on it.
    """
    query = _build_query(lat, lng, radius_m, cap=limit_each * 10)
    try:
        async with httpx.AsyncClient(timeout=18.0, headers=_HEADERS) as client:
            resp = await client.post(OVERPASS_URL, data={"data": query})
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
    except Exception:
        return [], []

    food: list[Place] = []
    fun: list[Place] = []
    seen: set[str] = set()
    for el in elements:
        place = _to_place(el)
        if place is None:
            continue
        key = f"{place.kind}:{place.name.strip().lower()}"
        if key in seen:
            continue
        seen.add(key)
        (food if place.kind == "food" else fun).append(place)

    def _dist(p: Place) -> float:
        return haversine_miles(lat, lng, p.lat, p.lng)

    # Food: nearest first. Fun: notable (wiki-tagged) first, then nearest.
    food.sort(key=_dist)
    fun.sort(key=lambda p: (not p.recommended, _dist(p)))
    return food[:limit_each], fun[:limit_each]
