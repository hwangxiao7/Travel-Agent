from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from app.config import settings
from app.models.schemas import Place, SocialPost
from app.services.geo import haversine_miles
from app.services.i18n import lang_name
from app.services.llm import generate_summary
from app.services.reddit_source import fetch_reddit_posts, reddit_available

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_HEADERS = {"User-Agent": "spontaneous-travel-agent/0.1 (dev)"}
# Nominatim category/type values that are really "good eats".
_FOOD_TYPES = {"restaurant", "cafe", "bar", "pub", "fast_food", "bakery", "ice_cream"}


def _tiktok_available() -> bool:
    return bool(settings.rapidapi_key and settings.rapidapi_tiktok_host)


def _xhs_available() -> bool:
    return bool(settings.rapidapi_key and settings.rapidapi_xhs_host)


def _instagram_available() -> bool:
    return bool(settings.rapidapi_key and settings.rapidapi_instagram_host)


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


def _parse_xhs_note(item: dict) -> SocialPost | None:
    """Tolerant parser across common Xiaohongshu/RED scraper response shapes."""
    if not isinstance(item, dict):
        return None
    # Some hosts nest the note under "note_card" / "note".
    node = item.get("note_card") or item.get("note") or item
    if not isinstance(node, dict):
        node = item
    title = node.get("title") or node.get("desc") or node.get("display_title") or ""
    if not title:
        return None

    user = node.get("user") or node.get("author") or {}
    if isinstance(user, dict):
        handle = user.get("nickname") or user.get("nick_name") or user.get("name") or ""
    else:
        handle = str(user)

    nid = node.get("note_id") or node.get("id") or item.get("id") or ""
    url = node.get("share_url") or node.get("url") or item.get("url") or ""
    if not url and nid:
        url = f"https://www.xiaohongshu.com/explore/{nid}"

    interact = node.get("interact_info") or {}
    likes = node.get("liked_count") or node.get("likes")
    if isinstance(interact, dict):
        likes = likes or interact.get("liked_count") or interact.get("like_count")

    cover = ""
    cov = node.get("cover") or node.get("image") or ""
    if isinstance(cov, dict):
        cover = cov.get("url") or cov.get("url_default") or ""
    elif isinstance(cov, str):
        cover = cov
    if not cover:
        images = node.get("images") or node.get("image_list") or []
        if isinstance(images, list) and images:
            first = images[0]
            cover = first.get("url", "") if isinstance(first, dict) else str(first)

    return SocialPost(
        title=str(title).strip()[:200],
        author=str(handle),
        url=str(url),
        likes=_as_int(likes),
        views=_as_int(node.get("view_count") or node.get("read_count")),
        thumbnail=str(cover),
        platform="xiaohongshu",
    )


async def fetch_xhs_guides(query: str, limit: int = 8) -> list[SocialPost]:
    """Search Xiaohongshu/RED for travel notes about a place.

    Best-effort: returns [] when no key/host is set or the API errors. The exact
    search path and params vary by RapidAPI provider — adjust for your host."""
    if not _xhs_available():
        return []

    host = settings.rapidapi_xhs_host
    url = f"https://{host}/search/notes"
    params = {"keyword": query, "keywords": query, "page": "1", "sort": "popularity"}
    headers = {"x-rapidapi-key": settings.rapidapi_key, "x-rapidapi-host": host}
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    body = data.get("data", data) if isinstance(data, dict) else {}
    notes = None
    for key in ("notes", "items", "list", "note_list", "data"):
        if isinstance(body, dict) and isinstance(body.get(key), list):
            notes = body[key]
            break
    if notes is None and isinstance(body, list):
        notes = body
    if not notes:
        return []

    posts: list[SocialPost] = []
    seen: set[str] = set()
    for item in notes:
        post = _parse_xhs_note(item)
        if post is None:
            continue
        key = post.title.lower()
        if key in seen:
            continue
        seen.add(key)
        posts.append(post)
    posts.sort(key=lambda p: p.likes, reverse=True)
    return posts[:limit]


def _parse_instagram_post(item: dict) -> SocialPost | None:
    """Tolerant parser across common Instagram scraper response shapes."""
    if not isinstance(item, dict):
        return None
    node = item.get("node") or item
    if not isinstance(node, dict):
        node = item
    caption = node.get("caption") or node.get("title") or node.get("text") or ""
    if isinstance(caption, dict):
        caption = caption.get("text") or caption.get("title") or ""
    if not caption:
        # Fall back to edge_media_to_caption shape.
        edges = (node.get("edge_media_to_caption") or {}).get("edges") or []
        if edges and isinstance(edges[0], dict):
            caption = (edges[0].get("node") or {}).get("text", "")
    if not caption:
        return None

    owner = node.get("owner") or node.get("user") or {}
    if isinstance(owner, dict):
        handle = owner.get("username") or owner.get("full_name") or ""
    else:
        handle = str(owner)

    code = node.get("shortcode") or node.get("code") or node.get("id") or ""
    url = node.get("url") or node.get("permalink") or ""
    if not url and code:
        url = f"https://www.instagram.com/p/{code}/"

    likes = node.get("like_count") or node.get("likes")
    if likes is None:
        likes = (node.get("edge_liked_by") or {}).get("count")

    cover = node.get("thumbnail_url") or node.get("display_url") or node.get("image") or ""
    if isinstance(cover, dict):
        cover = cover.get("url", "")

    return SocialPost(
        title=str(caption).strip()[:200],
        author=str(handle),
        url=str(url),
        likes=_as_int(likes),
        views=_as_int(node.get("view_count") or node.get("video_view_count")),
        thumbnail=str(cover),
        platform="instagram",
    )


async def fetch_instagram_guides(query: str, limit: int = 8) -> list[SocialPost]:
    """Search Instagram for travel posts about a place.

    Best-effort: returns [] when no key/host is set or the API errors. The exact
    search path and params vary by RapidAPI provider — adjust for your host."""
    if not _instagram_available():
        return []

    host = settings.rapidapi_instagram_host
    url = f"https://{host}/search"
    params = {"query": query, "q": query, "keyword": query}
    headers = {"x-rapidapi-key": settings.rapidapi_key, "x-rapidapi-host": host}
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    body = data.get("data", data) if isinstance(data, dict) else {}
    posts_raw = None
    for key in ("posts", "items", "results", "list", "medias", "data"):
        if isinstance(body, dict) and isinstance(body.get(key), list):
            posts_raw = body[key]
            break
    if posts_raw is None and isinstance(body, list):
        posts_raw = body
    if not posts_raw:
        return []

    posts: list[SocialPost] = []
    seen: set[str] = set()
    for item in posts_raw:
        post = _parse_instagram_post(item)
        if post is None:
            continue
        key = post.title.lower()
        if key in seen:
            continue
        seen.add(key)
        posts.append(post)
    posts.sort(key=lambda p: p.likes, reverse=True)
    return posts[:limit]


@dataclass(frozen=True)
class SocialProvider:
    """One pluggable social source. Add a platform = add one entry here.

    `authorized` = uses an official/licensed API (Reddit, YouTube). Unauthorized
    third-party scrapers (RapidAPI TikTok/IG/RED) are only enabled when the
    ENABLE_SOCIAL_SCRAPING dev gate is on, so production never depends on them.
    """

    name: str
    available: Callable[[], bool]
    fetch: Callable[[str], Awaitable[list[SocialPost]]]
    query: Callable[[str], str]  # dest_name -> platform-appropriate search query
    authorized: bool = False


_PROVIDERS: tuple[SocialProvider, ...] = (
    # AUTHORIZED official-API sources (safe for production / App Store).
    SocialProvider(
        "reddit",
        reddit_available,
        fetch_reddit_posts,
        lambda d: f"{d} things to do hidden gems recommendations",
        authorized=True,
    ),
    # UNAUTHORIZED third-party scrapers — dev-only, gated by ENABLE_SOCIAL_SCRAPING.
    SocialProvider(
        "tiktok",
        _tiktok_available,
        fetch_tiktok_guides,
        lambda d: f"{d} travel guide things to do",
    ),
    SocialProvider(
        "instagram",
        _instagram_available,
        fetch_instagram_guides,
        lambda d: f"{d} travel things to do",
    ),
    SocialProvider(
        "xiaohongshu",
        _xhs_available,
        fetch_xhs_guides,
        lambda d: f"{d} 攻略 好玩 探店",
    ),
)


def enabled_providers() -> list[SocialProvider]:
    """Authorized sources are always eligible; scrapers only when the dev gate is on."""
    out: list[SocialProvider] = []
    for p in _PROVIDERS:
        if not p.available():
            continue
        if p.authorized or settings.enable_social_scraping:
            out.append(p)
    return out


async def extract_viral_places(
    posts: list[SocialPost], dest_name: str, language: str
) -> list[tuple[str, str]]:
    """Pull concrete place names mentioned in posts.

    Returns (name_en, name_local) pairs: `name_en` is an English/romanized form
    that geocodes reliably; `name_local` is what travelers recognize (original
    script ok, e.g. from Chinese RED notes). Facts only — no post text is kept."""
    if not posts:
        return []
    corpus = "\n".join(f"- {p.title}" for p in posts[:12])
    prompt = (
        "You extract real, visitable place names (restaurants, cafes, shops, "
        "attractions, viewpoints, neighborhoods) mentioned in social travel posts.\n"
        f"Destination area: {dest_name}\n"
        'Return ONLY JSON like {"places": [{"name_en": "17-Mile Drive, Pebble Beach", '
        '"name_local": "十七英里"}]}.\n'
        "- name_en: English or romanized proper name that a map service can geocode; "
        "translate/transliterate if the post is in another language, and add the city "
        "when helpful.\n"
        "- name_local: the name as travelers would recognize it (original script ok).\n"
        "No emojis, no generic words like 'food' or 'view'. Max 8 items, deduplicated.\n\n"
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
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for it in names:
        if isinstance(it, dict):
            en = str(it.get("name_en") or "").strip()
            local = str(it.get("name_local") or en).strip()
        elif isinstance(it, str):
            en = local = it.strip()
        else:
            continue
        query = en or local
        if not (2 <= len(query) <= 80) or query.lower() in seen:
            continue
        seen.add(query.lower())
        out.append((query, local or query))
    # `language` reserved for future localized extraction; English names geocode best.
    _ = lang_name(language)
    return out[:8]


async def enrich_experiences(spots: list[Place], context: str, language: str) -> None:
    """Attach open-vocab experience tags + a neutral blurb to each spot, in place.

    Turns a bare "viral place" into an "experience" that a persona can match
    against (e.g. 抓小龙虾 → ["outdoor","foraging","water","hands-on"]). The blurb
    is a short neutral descriptor we generate — never copied post text."""
    if not spots:
        return
    names = "\n".join(f"- {s.name}" for s in spots)
    prompt = (
        "For each place, infer the EXPERIENCE it offers and label it for taste "
        "matching. Use open-vocabulary lowercase tags describing vibe/activity/"
        "audience/budget, e.g. outdoor, foraging, hands-on, water, hiking, food, "
        "nightlife, romantic, family, solo, quiet, hidden-gem, photography, "
        "adventure, relaxing, budget, luxury.\n"
        "Also write a neutral one-line blurb (your own words, no copied captions).\n"
        f"Context (social posts, for inference only):\n{context[:1500]}\n\n"
        f"Places:\n{names}\n\n"
        'Return ONLY JSON: {"items":[{"name":"...","tags":["..."],"blurb":"..."}]}. '
        "Max 6 tags each."
    )
    raw = await generate_summary(prompt, json_mode=True)
    if not raw:
        return
    try:
        obj = json.loads(raw)
        items = obj.get("items", []) if isinstance(obj, dict) else []
    except (json.JSONDecodeError, AttributeError):
        return
    by_name = {s.name.strip().lower(): s for s in spots}
    for it in items:
        if not isinstance(it, dict):
            continue
        spot = by_name.get(str(it.get("name", "")).strip().lower())
        if spot is None:
            continue
        tags = [str(t).strip().lower() for t in (it.get("tags") or []) if str(t).strip()]
        spot.experience_tags = list(dict.fromkeys(tags))[:6]
        blurb = str(it.get("blurb") or "").strip()
        if blurb:
            spot.blurb = blurb[:280]
    _ = lang_name(language)  # reserved for localized blurbs later


async def _geocode_near(
    client: httpx.AsyncClient, query: str, display: str, lat: float, lng: float, span: float
) -> Place | None:
    """Resolve one place name to coordinates, biased to a box around the dest.

    This is the legal firewall: a social mention only becomes a stored fact if it
    resolves to a real, authoritative OSM location near the destination."""
    params = {
        "q": query,
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
    label = (item.get("name") or "").strip() or display or query
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


async def _locate_sourced(
    name_sources: dict[str, set[str]],
    display_of: dict[str, str],
    lat: float,
    lng: float,
    radius_m: int = 30000,
    limit: int = 12,
) -> list[tuple[Place, set[str]]]:
    """Geocode extracted names and merge duplicates that resolve to the same spot.

    Returns (Place, platforms) pairs — platforms = which social sources mentioned
    it, so callers can cross-validate (mentioned on ≥2 platforms = higher trust).
    Sequential with light spacing to respect Nominatim's ~1 req/s policy."""
    if not name_sources:
        return []
    span = min(max(radius_m / 111_000.0, 0.05), 0.5)  # meters -> ~degrees, clamped
    by_key: dict[str, tuple[Place, set[str]]] = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i, (query, sources) in enumerate(list(name_sources.items())[:limit]):
            if i:
                await asyncio.sleep(1.05)
            place = await _geocode_near(client, query, display_of.get(query, query), lat, lng, span)
            if place is None:
                continue
            key = place.name.strip().lower()
            if key in by_key:
                by_key[key][1].update(sources)
            else:
                by_key[key] = (place, set(sources))
    out = list(by_key.values())
    out.sort(key=lambda ps: haversine_miles(lat, lng, ps[0].lat, ps[0].lng))
    return out


async def collect_social_signals(
    dest_name: str, lat: float, lng: float, language: str, limit: int = 12
) -> tuple[list[tuple[Place, set[str]]], list[SocialPost]]:
    """Fan out across all enabled social providers, distill to verified spots.

    Returns (located_spots_with_sources, raw_guides). The spots are the durable,
    fact-only asset; guides are for optional live display (never stored)."""
    providers = enabled_providers()
    if not providers:
        return [], []

    results = await asyncio.gather(
        *(p.fetch(p.query(dest_name)) for p in providers), return_exceptions=True
    )

    all_guides: list[SocialPost] = []
    name_sources: dict[str, set[str]] = {}
    display_of: dict[str, str] = {}
    for provider, result in zip(providers, results):
        posts = result if isinstance(result, list) else []
        if not posts:
            continue
        all_guides.extend(posts)
        pairs = await extract_viral_places(posts, dest_name, language)
        for query, display in pairs:
            name_sources.setdefault(query, set()).add(provider.name)
            display_of.setdefault(query, display)

    located = await _locate_sourced(name_sources, display_of, lat, lng)
    return located, all_guides


async def import_from_links(
    urls: list[str], lat: float, lng: float, dest_name: str, language: str
) -> tuple[list[tuple[Place, set[str]]], list["SocialEmbed"]]:
    """Compliant TikTok path: user-submitted links → official oEmbed → facts.

    Fetches each link via the platform's official oEmbed, extracts real place
    names from the caption, verifies + geocodes them against OSM, and returns
    (located_spots_with_sources, official_embeds). Embeds are for live display
    only; only the distilled spots are persisted by the caller."""
    from app.services.oembed import fetch_many  # local import avoids cycle

    embeds = await fetch_many(urls)
    if not embeds:
        return [], []
    name_sources: dict[str, set[str]] = {}
    display_of: dict[str, str] = {}
    for platform in {e.platform for e in embeds}:
        posts = [
            SocialPost(title=e.title, author=e.author, url=e.url, platform=e.platform)
            for e in embeds
            if e.platform == platform
        ]
        pairs = await extract_viral_places(posts, dest_name or "this area", language)
        for query, display in pairs:
            name_sources.setdefault(query, set()).add(platform)
            display_of.setdefault(query, display)
    located = await _locate_sourced(name_sources, display_of, lat, lng)
    await enrich_experiences(
        [p for p, _ in located], "\n".join(e.title for e in embeds), language
    )
    return located, embeds


async def import_from_text(
    texts: list[str],
    lat: float,
    lng: float,
    dest_name: str,
    language: str,
    platform: str = "xiaohongshu",
) -> list[tuple[Place, set[str]]]:
    """Compliant path for platforms without an oEmbed (e.g. Xiaohongshu/RED).

    The user pastes note text they copied themselves; we extract real place
    names, verify + geocode against OSM, and return located spots with the
    platform as provenance. Only facts are produced — the pasted text is used
    transiently for extraction and never persisted."""
    blocks = [t.strip() for t in texts if t and t.strip()]
    if not blocks:
        return []
    posts = [SocialPost(title=b[:2000], platform=platform) for b in blocks]
    pairs = await extract_viral_places(posts, dest_name or "this area", language)
    name_sources: dict[str, set[str]] = {}
    display_of: dict[str, str] = {}
    for query, display in pairs:
        name_sources.setdefault(query, set()).add(platform)
        display_of.setdefault(query, display)
    located = await _locate_sourced(name_sources, display_of, lat, lng)
    await enrich_experiences([p for p, _ in located], "\n".join(blocks), language)
    return located


async def social_highlights(
    dest_name: str, lat: float, lng: float, language: str
) -> tuple[list[SocialPost], list[Place]]:
    """Live multi-source highlights (TikTok/Instagram/RED) + the spots they mention.

    Best-effort fallback used when no ingested TrendingSpot rows exist yet.
    Returns ([], []) when no provider is configured."""
    located, guides = await collect_social_signals(dest_name, lat, lng, language)
    return guides, [place for place, _sources in located]
