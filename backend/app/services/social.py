from __future__ import annotations

import asyncio
import json

import httpx

from app.config import settings
from app.models.schemas import Place, SocialPost
from app.services.geo import haversine_miles
from app.services.i18n import lang_name
from app.services.llm import generate_summary

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_HEADERS = {"User-Agent": "spontaneous-travel-agent/0.1 (dev)"}
# Nominatim category/type values that are really "good eats".
_FOOD_TYPES = {"restaurant", "cafe", "bar", "pub", "fast_food", "bakery", "ice_cream"}


def _tiktok_available() -> bool:
    return bool(settings.rapidapi_key and settings.rapidapi_tiktok_host)


def _as_int(v: object) -> int:
    try:
        return int(float(v))  # handles "1234", 1234, 1234.0
    except (TypeError, ValueError):
        return 0


def _parse_video(item: dict) -> SocialPost | None:
    """Tolerant parser across common TikTok-scraper response shapes."""
    if not isinstance(item, dict):
        return None
    title = item.get("title") or item.get("desc") or item.get("description") or ""
    if not title:
        return None

    author = item.get("author") or {}
    if isinstance(author, dict):
        handle = author.get("unique_id") or author.get("uniqueId") or author.get("nickname") or ""
    else:
        handle = str(author)

    vid = item.get("video_id") or item.get("aweme_id") or item.get("id") or ""
    url = item.get("share_url") or item.get("url") or ""
    if not url and handle and vid:
        url = f"https://www.tiktok.com/@{handle}/video/{vid}"

    cover = ""
    if isinstance(item.get("cover"), str):
        cover = item["cover"]
    elif isinstance(item.get("origin_cover"), str):
        cover = item["origin_cover"]

    return SocialPost(
        title=title.strip()[:200],
        author=str(handle),
        url=url,
        likes=_as_int(item.get("digg_count") or item.get("like_count")),
        views=_as_int(item.get("play_count") or item.get("view_count")),
        thumbnail=cover,
        platform="tiktok",
    )


async def fetch_tiktok_guides(query: str, limit: int = 8) -> list[SocialPost]:
    """Search TikTok for travel-guide videos about a place.

    Best-effort: returns [] when no key/host is set or the API errors."""
    if not _tiktok_available():
        return []

    host = settings.rapidapi_tiktok_host
    url = f"https://{host}/feed/search"
    params = {
        "keywords": query,
        "count": str(limit),
        "cursor": "0",
        "region": "us",
        "publish_time": "0",
        "sort_type": "0",
    }
    headers = {"x-rapidapi-key": settings.rapidapi_key, "x-rapidapi-host": host}
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    # Find the list of videos regardless of the exact wrapper key.
    body = data.get("data", data) if isinstance(data, dict) else {}
    videos = None
    for key in ("videos", "aweme_list", "list", "items"):
        if isinstance(body, dict) and isinstance(body.get(key), list):
            videos = body[key]
            break
    if videos is None and isinstance(body, list):
        videos = body
    if not videos:
        return []

    posts: list[SocialPost] = []
    seen: set[str] = set()
    for item in videos:
        post = _parse_video(item)
        if post is None:
            continue
        key = post.title.lower()
        if key in seen:
            continue
        seen.add(key)
        posts.append(post)
    posts.sort(key=lambda p: p.views, reverse=True)
    return posts[:limit]


async def extract_viral_places(posts: list[SocialPost], dest_name: str, language: str) -> list[str]:
    """Ask the LLM to pull concrete place/shop names mentioned in the posts."""
    if not posts:
        return []
    corpus = "\n".join(f"- {p.title}" for p in posts[:12])
    prompt = (
        "You extract real, visitable place names (restaurants, cafes, shops, "
        "attractions, viewpoints, neighborhoods) mentioned in TikTok travel posts.\n"
        f"Destination area: {dest_name}\n"
        "Return ONLY a JSON object like {\"places\": [\"Name 1\", \"Name 2\"]}. "
        "Use the specific proper name, in English/original script, no emojis, no "
        "generic words like 'food' or 'view'. Max 8 items, deduplicated.\n\n"
        f"Posts:\n{corpus}"
    )
    raw = await generate_summary(prompt, json_mode=True)
    if not raw:
        return []
    try:
        obj = json.loads(raw)
        names = obj.get("places", []) if isinstance(obj, dict) else []
    except (json.JSONDecodeError, AttributeError):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for n in names:
        if not isinstance(n, str):
            continue
        name = n.strip()
        if 2 <= len(name) <= 60 and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    # `language` reserved for future localized extraction; English names geocode best.
    _ = lang_name(language)
    return out[:8]


async def _geocode_near(
    client: httpx.AsyncClient, name: str, lat: float, lng: float, span: float
) -> Place | None:
    """Resolve one place name to coordinates, biased to a box around the dest."""
    params = {
        "q": name,
        "format": "jsonv2",
        "limit": "1",
        "countrycodes": "us,ca",
        # viewbox = left,top,right,bottom (lon,lat) + bounded restricts to the box.
        "viewbox": f"{lng - span},{lat + span},{lng + span},{lat - span}",
        "bounded": "1",
    }
    try:
        resp = await client.get(_NOMINATIM_URL, params=params, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None
    if not data:
        return None
    item = data[0]
    try:
        plat, plng = float(item["lat"]), float(item["lon"])
    except (KeyError, ValueError):
        return None
    ptype = (item.get("type") or "").lower()
    kind = "food" if ptype in _FOOD_TYPES else "fun"
    label = (item.get("name") or "").strip() or name
    return Place(
        name=label,
        category="viral",
        kind=kind,  # type: ignore[arg-type]
        lat=plat,
        lng=plng,
        note="",
        recommended=True,
        trending=True,
    )


async def _locate_places(
    names: list[str], lat: float, lng: float, radius_m: int = 30000
) -> list[Place]:
    """Resolve extracted names to coordinates via Nominatim (indexed, fast).

    Sequential with light spacing to respect Nominatim's ~1 req/s policy."""
    if not names:
        return []
    span = min(max(radius_m / 111_000.0, 0.05), 0.5)  # meters -> ~degrees, clamped
    places: list[Place] = []
    seen: set[str] = set()
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i, name in enumerate(names[:6]):
            if i:
                await asyncio.sleep(1.05)
            place = await _geocode_near(client, name, lat, lng, span)
            if place is None:
                continue
            key = place.name.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            places.append(place)
    places.sort(key=lambda p: haversine_miles(lat, lng, p.lat, p.lng))
    return places


async def social_highlights(
    dest_name: str, lat: float, lng: float, language: str
) -> tuple[list[SocialPost], list[Place]]:
    """Fetch TikTok travel guides and the 🔥 spots they mention.

    Fully best-effort and opt-in: returns ([], []) with no key configured."""
    if not _tiktok_available():
        return [], []
    guides = await fetch_tiktok_guides(f"{dest_name} travel guide things to do")
    if not guides:
        return [], []
    names = await extract_viral_places(guides, dest_name, language)
    viral = await _locate_places(names, lat, lng)
    return guides, viral
