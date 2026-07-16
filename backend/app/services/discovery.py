"""Experience discovery: push fresh trending experiences that match a persona.

This is the "not a smart Google Map" part. Instead of listing nearby places,
we rank fresh EXPERIENCES by how well they fit the user's taste — a spot is
only pushed if it genuinely matches, proximity alone is not enough.

Matching is OPEN-VOCABULARY by design (architecture doc §2.2: "understand the
world, don't enumerate it"). There is NO maintained keyword/tag index for
ranking: we embed the user's (English-ified) ask and each experience's natural
-language blurb, and rank by cosine similarity. Tags, when present, are only
used for the human-readable reason and as a no-embeddings fallback — never as
a table you have to grow to cover new activities.
"""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.db import User
from app.models.schemas import ExperiencePush
from app.services.embeddings import embed_query, embed_texts
from app.services.experiences import season_multiplier
from app.services.trending_store import get_spots_near

_TOKEN_RE = re.compile(r"[a-z0-9\u4e00-\u9fff\-]+", re.I)
# Below this semantic fit, we do NOT push (avoids "nearby but irrelevant").
_MATCH_FLOOR = 0.20


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _persona(
    db: Session | None,
    user: User | None,
    preferences: list[str],
    interests: str,
) -> tuple[dict[str, float], str]:
    """Build (weighted persona tags, persona text) from explicit + historical signal."""
    tags: dict[str, float] = {}
    for p in preferences:
        tags[p.replace("_", "-").lower()] = 1.0
    for tok in _TOKEN_RE.findall((interests or "").lower()):
        if len(tok) >= 2:
            tags[tok] = max(tags.get(tok, 0.0), 1.0)

    text_bits: list[str] = []
    if interests:
        text_bits.append(interests)
    if preferences:
        text_bits.append(", ".join(p.replace("-", " ") for p in preferences))

    if db is not None and user is not None:
        try:
            from app.services.personalization import build_user_profile

            profile = build_user_profile(db, user)
            for a in profile.activity_preferences:
                tags[a.lower()] = max(tags.get(a.lower(), 0.0), 0.6)
            if profile.profile_text and "none yet" not in profile.profile_text.lower():
                text_bits.append(profile.profile_text)
        except Exception:
            pass

    return tags, ". ".join(text_bits) or "general local experiences"


async def _english_query(interests: str) -> str:
    """LLM-translate free-text interests (any language) → a short English phrase.

    The ONLY normalization we do — cross-language embeddings are weak (doc
    §2.2/§10), so we English-ify the ask ("户外 抓小龙虾" → "outdoor crayfishing")
    then embed it. Open vocabulary: no fixed tag list. Best-effort → "" on fail."""
    if not interests.strip():
        return ""
    # Shared core with llm_activity_phrase (loose contract: concrete phrase, not
    # a tight 2-5 word noun phrase). Local import avoids an import cycle.
    from app.services.query_understanding import english_activity_phrase

    return await english_activity_phrase(interests, strict=False)


def _overlap(spot_tags: list[str], persona: dict[str, float]) -> list[str]:
    """Free-form overlap for the human reason + no-embeddings fallback only.

    Not a maintained index — just whatever words the two sides happen to share."""
    if not spot_tags or not persona:
        return []
    return [t for t in spot_tags if t in persona]


def _reason(
    matched: list[str], blurb: str, platforms: list[str], fresh_days: int,
    in_season: bool, by_taste: bool, zh: bool
) -> str:
    # OSM is a data source, not a "someone posted" signal — phrase accordingly.
    social = [p for p in platforms if p != "osm"]
    src = "、".join(social) if social else ""
    if zh:
        parts = []
        if src:
            when = "最近" if fresh_days <= 21 else ""
            parts.append(f"{when}有人在 {src} 上提到" + (f"：{blurb}" if blurb else "附近的新玩法"))
        elif blurb:
            parts.append(blurb)
        if in_season:
            parts.append("正当季")
        if matched:
            parts.append("契合你偏好的 " + "、".join(matched[:3]))
        elif by_taste:
            parts.append("根据你一直喜欢的类型挑的")
        return "；".join(parts) + "。" if parts else "附近的新鲜体验。"
    parts = []
    if src:
        when = "recently " if fresh_days <= 21 else ""
        parts.append(f"{when}surfaced on {src}" + (f": {blurb}" if blurb else ""))
    elif blurb:
        parts.append(blurb)
    if in_season:
        parts.append("in season now")
    if matched:
        parts.append("matches your taste for " + ", ".join(matched[:3]))
    elif by_taste:
        parts.append("picked from what you usually enjoy")
    return "; ".join(parts) + "." if parts else "A fresh experience nearby."


async def recommend_experiences(
    db: Session | None,
    user: User | None,
    *,
    lat: float,
    lng: float,
    preferences: list[str],
    interests: str,
    radius_miles: int,
    language: str,
    k: int,
) -> tuple[list[ExperiencePush], list[str]]:
    persona_tags, persona_text = _persona(db, user, preferences, interests)
    # English-ify the free-text ask (only normalization; open vocabulary).
    en_query = await _english_query(interests)

    # "我知道你喜欢什么": persistent taste vector (who the user is), if logged in.
    taste_vec = None
    if db is not None and user is not None:
        try:
            from app.services.taste_profile import build_taste_profile

            taste_vec = (await build_taste_profile(db, user)).vector
        except Exception:
            taste_vec = None

    candidates = get_spots_near(lat, lng, radius_miles, limit=80)
    if not candidates:
        return [], sorted(persona_tags)

    # Ranking is pure semantic (no keyword index): embed the ask + the taste
    # vector, compare against each spot's natural-language blurb.
    has_query = bool((en_query or interests).strip())
    qvec = await embed_query(en_query or interests.strip()) if has_query else None
    exp_texts = [
        f"{c['place'].name}. {c['place'].blurb} {' '.join(c['place'].experience_tags)}".strip()
        for c in candidates
    ]
    exp_vecs = await embed_texts(exp_texts) if (qvec is not None or taste_vec is not None) else None

    zh = language.lower().startswith("zh")
    month = datetime.utcnow().month
    pushes: list[ExperiencePush] = []
    for i, c in enumerate(candidates):
        place = c["place"]
        matched = _overlap(place.experience_tags, persona_tags)  # for reason/fallback only
        by_taste = False
        if exp_vecs is not None:
            sim_q = _cosine(qvec, exp_vecs[i]) if qvec is not None else None
            sim_t = _cosine(taste_vec, exp_vecs[i]) if taste_vec is not None else None
            if sim_q is not None and sim_t is not None:
                match = 0.6 * sim_q + 0.4 * sim_t  # ask leads, taste personalizes
            elif sim_t is not None:
                match, by_taste = sim_t, True  # no ask → taste decides ("不知道做什么")
            else:
                match = sim_q or 0.0
        else:
            # No embeddings available → degrade to free-form word overlap.
            match = min(1.0, 0.3 * len(matched)) if matched else 0.0
        if match < _MATCH_FLOOR:
            continue
        fresh_days = c["freshness_days"]
        freshness = 1.0 / (1.0 + fresh_days / 14.0)
        proximity = max(0.0, 1.0 - c["distance_miles"] / max(radius_miles, 1))
        # Seasonality: down-weight off-season experiences (e.g. cherry picking in Dec).
        season = season_multiplier(place.category, month)
        final = (0.7 * match + 0.15 * freshness + 0.15 * proximity) * season
        pushes.append(
            ExperiencePush(
                name=place.name,
                lat=place.lat,
                lng=place.lng,
                kind=place.kind,
                blurb=place.blurb,
                experience_tags=place.experience_tags,
                platforms=c["platforms"],
                distance_miles=c["distance_miles"],
                freshness_days=fresh_days,
                match_score=round(final, 3),
                reason=_reason(
                    matched, place.blurb, c["platforms"], fresh_days, season >= 1.0, by_taste, zh
                ),
            )
        )
    pushes.sort(key=lambda p: p.match_score, reverse=True)
    return pushes[:k], sorted(persona_tags)
