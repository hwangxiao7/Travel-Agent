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
# shop=* values that are really "good eats" (indie bakeries, coffee roasters, etc.)
FOOD_SHOPS = {"bakery", "pastry", "confectionery", "deli", "coffee", "chocolate", "cheese"}
# tourism=* / leisure=* values treated as "fun"
FUN_TOURISM = {"attraction", "viewpoint", "museum", "artwork", "theme_park", "zoo", "aquarium", "gallery"}
FUN_LEISURE = {"park", "nature_reserve", "garden"}
# Niche / offbeat "fun": historic sites, indie shops, markets, small venues.
FUN_HISTORIC = {"monument", "memorial", "castle", "ruins", "archaeological_site", "fort", "tower"}
FUN_SHOPS = {"books", "art", "antiques", "craft", "music", "second_hand"}
FUN_AMENITIES = {"marketplace", "arts_centre", "theatre", "cinema"}

# Map raw OSM tag values -> stable machine category keys the frontend can localize.
_CATEGORY = {
    "restaurant": "restaurant",
    "cafe": "cafe",
    "fast_food": "fast_food",
    "bar": "bar",
    "pub": "bar",
    "ice_cream": "ice_cream",
    "food_court": "restaurant",
    # food shops
    "bakery": "bakery",
    "pastry": "bakery",
    "confectionery": "sweets",
    "chocolate": "sweets",
    "deli": "deli",
    "coffee": "cafe",
    "cheese": "deli",
    # fun / tourism
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
    # niche fun
    "monument": "historic",
    "memorial": "historic",
    "castle": "historic",
    "ruins": "historic",
    "archaeological_site": "historic",
    "fort": "historic",
    "tower": "historic",
    "books": "shop",
    "art": "shop",
    "antiques": "shop",
    "craft": "shop",
    "music": "shop",
    "second_hand": "shop",
    "marketplace": "market",
    "arts_centre": "theatre",
    "theatre": "theatre",
    "cinema": "theatre",
    # walkable
    "square": "walk",
    "pedestrian": "walk",
}


def _build_query(lat: float, lng: float, radius_m: int, cap: int) -> str:
    r = radius_m
    food_a = "|".join(sorted(FOOD_AMENITIES))
    food_s = "|".join(sorted(FOOD_SHOPS))
    tourism = "|".join(sorted(FUN_TOURISM))
    leisure = "|".join(sorted(FUN_LEISURE))
    historic = "|".join(sorted(FUN_HISTORIC))
    fun_s = "|".join(sorted(FUN_SHOPS))
    fun_a = "|".join(sorted(FUN_AMENITIES))
    return (
        f"[out:json][timeout:20];"
        f"("
        f'node["amenity"~"^({food_a})$"]["name"](around:{r},{lat},{lng});'
        f'node["shop"~"^({food_s})$"]["name"](around:{r},{lat},{lng});'
        f'node["tourism"~"^({tourism})$"]["name"](around:{r},{lat},{lng});'
        f'node["leisure"~"^({leisure})$"]["name"](around:{r},{lat},{lng});'
        f'node["historic"~"^({historic})$"]["name"](around:{r},{lat},{lng});'
        f'node["shop"~"^({fun_s})$"]["name"](around:{r},{lat},{lng});'
        f'node["amenity"~"^({fun_a})$"]["name"](around:{r},{lat},{lng});'
        f'node["place"="square"]["name"](around:{r},{lat},{lng});'
        f'way["highway"="pedestrian"]["name"](around:{r},{lat},{lng});'
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
    shop = tags.get("shop")
    if amenity in FOOD_AMENITIES or shop in FOOD_SHOPS:
        kind = "food"
        raw = amenity if amenity in FOOD_AMENITIES else shop
        note = tags.get("cuisine", "").replace("_", " ").replace(";", ", ")
    else:
        kind = "fun"
        raw = (
            tags.get("tourism")
            or tags.get("historic")
            or shop
            or amenity
            or tags.get("leisure")
            or ("pedestrian" if tags.get("highway") == "pedestrian" else "")
            or ("square" if tags.get("place") == "square" else "")
            or "attraction"
        )
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

    # Food: notable first, then nearest.
    food.sort(key=lambda p: (not p.recommended, _dist(p)))
    # Fun: notable first, then nearest — but diversify categories so niche spots
    # (historic, indie shops, markets, walks) surface instead of six parks.
    fun.sort(key=lambda p: (not p.recommended, _dist(p)))
    return _diversify(food, limit_each), _diversify(fun, limit_each)


def _diversify(places: list[Place], limit: int, max_per_cat: int = 2) -> list[Place]:
    """Pick up to `limit`, capping each category so results stay varied.
    Falls back to filling remaining slots in original order."""
    picked: list[Place] = []
    counts: dict[str, int] = {}
    leftovers: list[Place] = []
    for p in places:
        if counts.get(p.category, 0) < max_per_cat:
            picked.append(p)
            counts[p.category] = counts.get(p.category, 0) + 1
        else:
            leftovers.append(p)
        if len(picked) >= limit:
            return picked
    for p in leftovers:
        if len(picked) >= limit:
            break
        picked.append(p)
    return picked
