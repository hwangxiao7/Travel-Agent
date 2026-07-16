"""Resolve concrete nearby venues for a picked ACTIVITY (娱乐项目 → 地点).

Activities stay shop-independent until the user picks one. Then we look up
real places near their origin:

1. Local trending/OSM store (category / tag match) — fast, already verified.
2. Nominatim text search with curated English venue phrases per activity
   (e.g. farm_animals → petting farm / zoo / cat cafe).

Venue phrases are resolution hints (how to find a place), not a ranking
synonym index — ranking of activities stays open-vocab embeddings.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.services.activity_catalog import ACTIVITY_BY_KEY, Activity
from app.services.geo import estimate_drive_hours, format_duration, haversine_miles
from app.services.poi_search import _nominatim_search

# Multi-phrase venue search per activity. Order = preference.
# Keep English; Nominatim is English-biased for US/CA.
_VENUE_QUERIES: dict[str, tuple[str, ...]] = {
    "paragliding": ("paragliding", "hang gliding"),
    "skydiving": ("skydiving", "drop zone"),
    "zipline": ("zipline", "zip line"),
    "hot_air_balloon": ("hot air balloon", "balloon ride"),
    "go_kart": ("go kart", "karting"),
    "indoor_climbing": ("climbing gym", "bouldering"),
    "axe_throwing": ("axe throwing",),
    "archery": ("archery range", "archery"),
    "shooting_range": ("shooting range", "gun range"),
    "surfing": ("surf school", "surf shop"),
    "trampoline": ("trampoline park",),
    "sup": ("paddleboard rental", "stand up paddleboard"),
    "kayak": ("kayak rental", "kayaking"),
    "whale_watching": ("whale watching",),
    "crayfishing": ("fishing pier", "fishing pond", "fishing"),
    "snorkeling": ("snorkeling", "dive shop"),
    "rafting": ("rafting", "river rafting"),
    "sailing": ("sailing charter", "sailboat rental"),
    "hot_spring": ("hot spring", "hot springs"),
    "camping": ("campground", "camping"),
    "hiking": ("hiking trailhead", "trailhead", "regional park"),
    "cycling": ("bike path", "bike rental"),
    "picnic": ("park", "picnic area", "public garden"),
    "sunset_view": ("viewpoint", "scenic overlook"),
    "stargazing": ("observatory", "dark sky"),
    "botanical_garden": ("botanical garden", "flower garden"),
    "u_pick": ("u-pick", "pick your own", "berry farm"),
    "farm_animals": ("petting farm", "petting zoo", "animal sanctuary", "zoo", "cat cafe"),
    "horse_riding": ("horseback riding", "riding stable"),
    "pottery": ("pottery class", "ceramics studio"),
    "painting": ("art class", "paint and sip"),
    "floral": ("floral workshop", "flower arranging"),
    "baking": ("baking class", "cooking school"),
    "candle_diy": ("candle making", "candle workshop"),
    "cooking_class": ("cooking class", "culinary school"),
    "escape_room": ("escape room",),
    "board_games": ("board game cafe", "board game café"),
    "ktv": ("karaoke", "karaoke bar"),
    "bowling": ("bowling alley", "bowling"),
    "arcade": ("arcade", "barcade"),
    "roller_skating": ("roller rink", "roller skating"),
    "mini_golf": ("mini golf", "miniature golf"),
    "comedy": ("comedy club",),
    "live_music": ("live music venue", "concert hall"),
    "open_air_cinema": ("outdoor cinema", "drive-in theater"),
    "museum": ("museum", "art museum"),
    "bookstore_cafe": ("bookstore cafe", "independent bookstore"),
    "flea_market": ("flea market", "vintage market"),
    "farmers_market": ("farmers market", "farmers' market"),
    "yoga": ("yoga studio", "yoga class"),
    "boxing": ("boxing gym", "martial arts"),
    "meditation": ("meditation center", "sound bath"),
}


# Activities that are inherently tied to specific geography (coast, river, dark
# sky, geology, rural farms/dropzones). For these, venues tens of miles away are
# expected and fine. Everything NOT listed here is "ubiquitous" — doable near
# almost any town — so we bias hard toward the closest option.
_GEO_CONSTRAINED: frozenset[str] = frozenset(
    {
        "surfing",
        "snorkeling",
        "whale_watching",
        "sailing",
        "rafting",
        "kayak",
        "sup",
        "hot_spring",
        "skydiving",
        "paragliding",
        "hot_air_balloon",
        "horse_riding",
        "stargazing",
        "camping",
        "u_pick",
        "farm_animals",
        "zipline",
    }
)

# Effective search radius for ubiquitous activities (miles). Kept small so the
# viewbox is local and the nearest venue actually surfaces.
_LOCAL_RADIUS_MILES = 15.0


@dataclass
class ActivityVenue:
    name: str
    lat: float
    lng: float
    distance_miles: float
    drive_time: str
    source: str  # trending | nominatim
    query: str
    blurb: str = ""


def venue_queries_for(activity: Activity) -> tuple[str, ...]:
    qs = _VENUE_QUERIES.get(activity.key)
    if qs:
        return qs
    return (activity.name_en,)


def _from_trending(
    activity: Activity,
    *,
    lat: float,
    lng: float,
    radius_miles: float,
    limit: int,
) -> list[ActivityVenue]:
    """Pull already-ingested spots whose category/tags align with this activity."""
    try:
        from app.services.trending_store import get_spots_near
    except Exception:
        return []

    needles = {q.lower() for q in venue_queries_for(activity)}
    needles.add(activity.key.replace("_", " "))
    needles.add(activity.name_en.lower())

    out: list[ActivityVenue] = []
    seen: set[str] = set()
    for row in get_spots_near(lat, lng, radius_miles, limit=80):
        place = row["place"]
        name_l = place.name.lower()
        cat = (place.category or "").lower().replace("-", "_")
        blob = f"{name_l} {place.blurb}".lower()
        # Strict local match only — vibe-tag overlap is too noisy (e.g. "water").
        hit = cat == activity.key or any(n in blob for n in needles if len(n) >= 4)
        if not hit:
            continue
        key = name_l
        if key in seen:
            continue
        seen.add(key)
        miles = float(row["distance_miles"])
        out.append(
            ActivityVenue(
                name=place.name,
                lat=place.lat,
                lng=place.lng,
                distance_miles=miles,
                drive_time=format_duration(estimate_drive_hours(miles)),
                source="trending",
                query=activity.key,
                blurb=place.blurb or "",
            )
        )
        if len(out) >= limit:
            break
    return out


async def _from_nominatim(
    phrases: tuple[str, ...],
    *,
    lat: float,
    lng: float,
    radius_miles: float,
    limit: int,
    exclude: set[str],
    pool: int = 40,
) -> list[ActivityVenue]:
    """Search Nominatim and return the CLOSEST matches.

    Nominatim orders by "importance", which surfaces big named regional parks
    over the ordinary park down the street. We pull a larger candidate pool and
    re-rank by distance so nearby venues win.
    """
    deg = max(0.12, min(1.8, radius_miles / 55.0))
    viewbox = f"{lng - deg},{lat + deg},{lng + deg},{lat - deg}"
    cand: list[ActivityVenue] = []
    seen = set(exclude)

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            for phrase in phrases:
                try:
                    data = await _nominatim_search(
                        client, search_q=phrase, viewbox=viewbox, limit=pool
                    )
                except Exception:
                    continue
                for item in data:
                    try:
                        plat = float(item["lat"])
                        plng = float(item["lon"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    miles = haversine_miles(lat, lng, plat, plng)
                    if miles > radius_miles + 2:
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
                    cand.append(
                        ActivityVenue(
                            name=name,
                            lat=plat,
                            lng=plng,
                            distance_miles=round(miles, 1),
                            drive_time=format_duration(estimate_drive_hours(miles)),
                            source="nominatim",
                            query=phrase,
                            blurb=(f"Near {locality}" if locality else f"Found for “{phrase}”"),
                        )
                    )
    except Exception:
        pass

    cand.sort(key=lambda v: v.distance_miles)
    return cand[:limit]


async def resolve_venues(
    activity_key: str,
    *,
    lat: float,
    lng: float,
    radius_miles: float = 40.0,
    k: int = 6,
) -> tuple[Activity, list[ActivityVenue]]:
    activity = ACTIVITY_BY_KEY.get(activity_key)
    if activity is None:
        raise ValueError(f"Unknown activity: {activity_key}")

    # Ubiquitous activities (picnic, museum, bowling…) should stay close: search
    # a tight radius first so the nearest venue wins. Geo-constrained ones
    # (surfing, hot springs…) keep the full radius — far is expected there.
    constrained = activity_key in _GEO_CONSTRAINED
    eff_radius = radius_miles if constrained else min(radius_miles, _LOCAL_RADIUS_MILES)

    async def _gather(search_radius: float) -> list[ActivityVenue]:
        local = _from_trending(
            activity, lat=lat, lng=lng, radius_miles=search_radius, limit=k
        )
        need = max(0, k - len(local))
        remote: list[ActivityVenue] = []
        if need:
            exclude = {v.name.lower() for v in local}
            remote = await _from_nominatim(
                venue_queries_for(activity),
                lat=lat,
                lng=lng,
                radius_miles=search_radius,
                limit=need,
                exclude=exclude,
            )
        merged = local + remote
        merged.sort(key=lambda v: v.distance_miles)
        return merged[:k]

    result = await _gather(eff_radius)

    # Sparse area (e.g. rural): if the tight local search found nothing, widen
    # once to the full requested radius rather than returning an empty list.
    if not result and eff_radius < radius_miles:
        result = await _gather(radius_miles)

    return activity, result
