"""Reddit discovery source — AUTHORIZED (official API).

This is the compliant counterpart to the RapidAPI scrapers: it uses Reddit's
official OAuth API to read public discussions, from which the ingestion pipeline
extracts real place names + experience signals. We keep only derived facts and a
source_reference (permalink) for attribution — never mirrored post content.

Application-only OAuth (client_credentials) gives read-only access to public
listings; no user login required. Best-effort: no creds → [].
"""

from __future__ import annotations

import time

import httpx

from app.config import settings
from app.models.schemas import SocialPost

_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_SEARCH_URL = "https://oauth.reddit.com/search"

# Simple in-process token cache (access_token, expires_at_epoch).
_token: tuple[str, float] | None = None


def reddit_available() -> bool:
    return bool(settings.reddit_client_id and settings.reddit_client_secret)


async def _get_token(client: httpx.AsyncClient) -> str | None:
    global _token
    if _token and _token[1] - 30 > time.time():
        return _token[0]
    try:
        resp = await client.post(
            _TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(settings.reddit_client_id, settings.reddit_client_secret),
            headers={"User-Agent": settings.reddit_user_agent},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None
    tok = data.get("access_token")
    if not tok:
        return None
    _token = (tok, time.time() + float(data.get("expires_in", 3600)))
    return tok


def _parse_post(child: dict) -> SocialPost | None:
    if not isinstance(child, dict):
        return None
    data = child.get("data") or {}
    if not isinstance(data, dict) or data.get("over_18"):
        return None
    title = data.get("title") or ""
    if not title:
        return None
    # Feed title + a slice of the discussion body to the extractor (not stored).
    body = data.get("selftext") or ""
    text = f"{title}. {body}".strip()

    permalink = data.get("permalink") or ""
    url = f"https://www.reddit.com{permalink}" if permalink else (data.get("url") or "")
    subreddit = data.get("subreddit") or ""

    return SocialPost(
        title=text[:500],
        # Attribution = the community, not an individual user handle.
        author=f"r/{subreddit}" if subreddit else "reddit",
        url=url,
        likes=int(data.get("score") or 0),
        views=int(data.get("num_comments") or 0),
        thumbnail="",
        platform="reddit",
    )


async def fetch_reddit_posts(query: str, limit: int = 12) -> list[SocialPost]:
    """Search public Reddit discussions for a place/experience query."""
    if not reddit_available():
        return []
    headers = {"User-Agent": settings.reddit_user_agent}
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            token = await _get_token(client)
            if not token:
                return []
            headers["Authorization"] = f"bearer {token}"
            resp = await client.get(
                _SEARCH_URL,
                params={
                    "q": query,
                    "limit": str(limit),
                    "sort": "relevance",
                    "type": "link",
                    "t": "year",  # recency: past year
                },
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    children = (data.get("data") or {}).get("children") or []
    posts: list[SocialPost] = []
    seen: set[str] = set()
    for child in children:
        post = _parse_post(child)
        if post is None:
            continue
        key = post.title.lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        posts.append(post)
    posts.sort(key=lambda p: p.likes, reverse=True)
    return posts[:limit]
