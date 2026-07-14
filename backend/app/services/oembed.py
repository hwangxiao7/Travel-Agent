"""Official oEmbed fetchers — the compliant way to use social posts.

Instead of scraping, the user submits a post URL and we call the platform's
OFFICIAL oEmbed endpoint. From the returned caption we extract real place names
(facts, stored), and we return the official embed HTML for display (rendered
live, never persisted). This satisfies the compliance doc §7.4 / §11.3:
"user submitted links" + "display via official embed, don't copy content".

TikTok oEmbed is public and keyless. Instagram/Facebook oEmbed require a Meta
app token (add later); unknown hosts return None.
"""

from __future__ import annotations

import httpx

from app.models.schemas import SocialEmbed

_TIKTOK_OEMBED = "https://www.tiktok.com/oembed"
_HEADERS = {"User-Agent": "local-discovery/0.1 (dev)"}


def platform_of(url: str) -> str:
    u = url.lower()
    if "tiktok.com" in u:
        return "tiktok"
    if "instagram.com" in u:
        return "instagram"
    if "xiaohongshu.com" in u or "xhslink.com" in u:
        return "xiaohongshu"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    return ""


async def _fetch_tiktok(client: httpx.AsyncClient, url: str) -> SocialEmbed | None:
    try:
        resp = await client.get(_TIKTOK_OEMBED, params={"url": url}, headers=_HEADERS)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None
    title = data.get("title") or ""
    if not title:
        return None
    return SocialEmbed(
        platform="tiktok",
        url=url,
        title=str(title)[:300],
        author=str(data.get("author_name") or ""),
        thumbnail=str(data.get("thumbnail_url") or ""),
        html=str(data.get("html") or ""),
    )


async def fetch_oembed(client: httpx.AsyncClient, url: str) -> SocialEmbed | None:
    """Resolve one submitted URL to an official embed (caption + iframe html)."""
    platform = platform_of(url)
    if platform == "tiktok":
        return await _fetch_tiktok(client, url)
    # Other platforms (Instagram/YouTube) need their own official tokens/APIs.
    return None


async def fetch_many(urls: list[str], limit: int = 12) -> list[SocialEmbed]:
    out: list[SocialEmbed] = []
    seen: set[str] = set()
    async with httpx.AsyncClient(timeout=12.0) as client:
        for url in urls[:limit]:
            url = url.strip()
            if not url or url in seen:
                continue
            seen.add(url)
            embed = await fetch_oembed(client, url)
            if embed is not None:
                out.append(embed)
    return out
