"""Experience taxonomy + OSM-sourced experience discovery (no social needed).

Activities like crayfishing or cherry picking don't need social posts — they
live in OpenStreetMap as structured tags, and their "when" is seasonality
(world knowledge). This module:

1. Defines an experience taxonomy: concept → OSM selectors + experience_tags +
   in-season months.
2. Queries Overpass for real, geocoded, verifiable spots.
3. Classifies each spot to an experience type and produces Place objects with
   experience_tags + a neutral blurb — ready for the same persona-matched push
   pipeline (trending_store + discovery). Provenance platform = "osm".

Seasonality is applied later at serve time (see season_multiplier), so a spot
stored in July can be down-weighted in December without being deleted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from app.models.schemas import Place

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_HEADERS = {"User-Agent": "spontaneous-travel-agent/0.1 (dev)"}

# Filter value forms:
#   ("key", "value")        exact match
#   ("key", ("a", "b"))     any-of (regex)
#   ("key", None)           key present with any value
Filter = tuple[str, "str | tuple[str, ...] | None"]


@dataclass(frozen=True)
class ExperienceType:
    key: str
    label: str
    kind: str  # "food" | "fun"
    filters: tuple[Filter, ...]
    tags: tuple[str, ...]  # experience_tags for persona matching
    months: tuple[int, ...] = field(default_factory=tuple)  # in-season (empty = year-round)


# Northern-hemisphere seasons (rough); product is North America.
EXPERIENCE_TYPES: tuple[ExperienceType, ...] = (
    ExperienceType(
        "fishing", "Fishing & crayfishing", "fun",
        (("leisure", "fishing"), ("fishing", "yes")),
        ("fishing", "outdoor", "water", "foraging", "hands-on", "relaxing"),
        (5, 6, 7, 8, 9),
    ),
    ExperienceType(
        "u_pick", "Fruit & berry picking (U-pick)", "fun",
        # Exact-match tags only — "key present" filters (produce/crop) make
        # Overpass do full scans and time out.
        (("shop", "farm"), ("landuse", "orchard"), ("farm", "pick_your_own")),
        ("outdoor", "foraging", "family", "seasonal", "hands-on"),
        (5, 6, 7, 8, 9, 10),
    ),
    ExperienceType(
        "hot_spring", "Hot springs", "fun",
        (("natural", "hot_spring"), ("bath:type", "hot_spring")),
        ("outdoor", "water", "relaxing", "nature"),
        (),  # year-round
    ),
    ExperienceType(
        "farmers_market", "Farmers market", "food",
        (("amenity", "marketplace"),),
        ("food", "local", "family", "walkable"),
        (5, 6, 7, 8, 9, 10),
    ),
    ExperienceType(
        "winery", "Winery & tasting", "food",
        (("craft", "winery"), ("tourism", "wine_cellar")),
        ("food", "relaxing", "date", "scenic"),
        (),
    ),
    ExperienceType(
        "botanical_garden", "Botanical garden", "fun",
        (("leisure", "garden"), ("garden:type", "botanical")),
        ("outdoor", "quiet", "photography", "relaxing", "nature"),
        (4, 5, 6, 7, 8, 9, 10),
    ),
    ExperienceType(
        "observatory", "Stargazing & observatory", "fun",
        (("man_made", "observatory"), ("amenity", "observatory")),
        ("night", "quiet", "outdoor", "science"),
        (),
    ),
)

_BY_KEY = {e.key: e for e in EXPERIENCE_TYPES}


def _filter_to_overpass(f: Filter) -> str:
    key, val = f
    if val is None:
        return f'["{key}"]'
    if isinstance(val, tuple):
        return f'["{key}"~"^({"|".join(val)})$"]'
    return f'["{key}"="{val}"]'


def _type_query(exp: ExperienceType, lat: float, lng: float, radius_m: int, cap: int) -> str:
    """One lightweight query for a single experience type (reliable on public Overpass)."""
    parts: list[str] = []
    for f in exp.filters:
        frag = _filter_to_overpass(f)
        parts.append(f'node{frag}["name"](around:{radius_m},{lat},{lng});')
        parts.append(f'way{frag}["name"](around:{radius_m},{lat},{lng});')
    return f'[out:json][timeout:40];({"".join(parts)});out center {cap};'


def build_query(lat: float, lng: float, radius_m: int, cap: int = 120) -> str:
    """Combined query (all types). Kept for tests; production uses per-type queries."""
    parts: list[str] = []
    seen: set[str] = set()
    for exp in EXPERIENCE_TYPES:
        for f in exp.filters:
            frag = _filter_to_overpass(f)
            if frag in seen:
                continue
            seen.add(frag)
            parts.append(f'node{frag}["name"](around:{radius_m},{lat},{lng});')
            parts.append(f'way{frag}["name"](around:{radius_m},{lat},{lng});')
    return f'[out:json][timeout:40];({"".join(parts)});out center {cap};'


def _match(exp: ExperienceType, tags: dict) -> bool:
    for key, val in exp.filters:
        got = tags.get(key)
        if got is None:
            continue
        if val is None:
            return True
        if isinstance(val, tuple):
            if got in val:
                return True
        elif got == val:
            return True
    return False


def classify(tags: dict) -> ExperienceType | None:
    """First experience type (in taxonomy order) whose filters match the tags."""
    for exp in EXPERIENCE_TYPES:
        if _match(exp, tags):
            return exp
    return None


def season_multiplier(exp_key: str, month: int) -> float:
    """1.0 in season / year-round; 0.6 adjacent month; 0.25 off-season."""
    exp = _BY_KEY.get(exp_key)
    if exp is None or not exp.months:
        return 1.0
    if month in exp.months:
        return 1.0
    adjacent = {((m % 12) + 1) for m in exp.months} | {((m - 2) % 12) + 1 for m in exp.months}
    return 0.6 if month in adjacent else 0.25


def is_experience_category(category: str) -> bool:
    return category in _BY_KEY


def _to_place(el: dict) -> Place | None:
    tags = el.get("tags", {})
    name = tags.get("name")
    if not name:
        return None
    lat = el.get("lat") or el.get("center", {}).get("lat")
    lng = el.get("lon") or el.get("center", {}).get("lon")
    if lat is None or lng is None:
        return None
    exp = classify(tags)
    if exp is None:
        return None
    return Place(
        name=name,
        category=exp.key,  # experience type key (drives seasonality at serve time)
        kind=exp.kind,  # type: ignore[arg-type]
        lat=float(lat),
        lng=float(lng),
        note="",
        recommended="wikidata" in tags or "wikipedia" in tags,
        trending=True,
        experience_tags=list(exp.tags),
        blurb=f"{exp.label} at {name}.",
    )


async def fetch_osm_experiences(
    lat: float, lng: float, radius_m: int = 40000, cap: int = 60
) -> list[Place]:
    """Query Overpass per experience type near a coordinate. Best-effort → [].

    One small query per type is far more reliable than a single wide union
    (which 504s / server-side-times-out on the public endpoint)."""
    import asyncio

    # Cap radius: wide-area scans time out on the shared Overpass endpoint.
    radius_m = min(radius_m, 30000)
    places: list[Place] = []
    seen: set[str] = set()
    async with httpx.AsyncClient(timeout=50.0, headers=_HEADERS) as client:
        for i, exp in enumerate(EXPERIENCE_TYPES):
            if i:
                await asyncio.sleep(1.0)  # be polite between per-type queries
            query = _type_query(exp, lat, lng, radius_m, cap)
            try:
                resp = await client.post(OVERPASS_URL, data={"data": query})
                resp.raise_for_status()
                elements = resp.json().get("elements", [])
            except Exception:
                continue
            for el in elements:
                place = _to_place(el)
                if place is None:
                    continue
                key = f"{place.category}:{place.name.strip().lower()}"
                if key in seen:
                    continue
                seen.add(key)
                places.append(place)
    return places
