"""Activity recommendation: push shop-independent 娱乐项目 by taste + context.

Answers "不知道今天/小长假干嘛" with an ACTIVITY (+ a rough plan), not a shop.
Ranking is open-vocab semantic (taste/ask vs each activity's blurb) modulated by
season and soft context (companion / energy / budget / weather). Never keyword
tables, never dead-ends: with no signal it still returns season-appropriate ideas.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db import User
from app.models.schemas import ActivitySuggestion
from app.services.activity_catalog import ACTIVITIES, Activity
from app.services.embeddings import embed_query, embed_texts

_ENERGY = {"low": 0, "medium": 1, "high": 2}
_COST = {"$": 0, "$$": 1, "$$$": 2}

# Soft buckets for cold-start diversity (not a matching keyword index).
_THRILL_TAGS = frozenset({"thrill", "adventure", "bucket-list"})
_CHILL_TAGS = frozenset(
    {
        "relaxing",
        "cozy",
        "scenic",
        "social",
        "playful",
        "creative",
        "food",
        "culture",
        "quiet",
        "aesthetic",
        "wholesome",
        "chill",
        "wellness",
        "local",
        "nature",
    }
)


def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _season_mult(a: Activity, month: int) -> float:
    if not a.months:
        return 1.0
    if month in a.months:
        return 1.0
    adjacent = {((m % 12) + 1) for m in a.months} | {((m - 2) % 12) + 1 for m in a.months}
    return 0.6 if month in adjacent else 0.25


def _context_mult(a: Activity, *, companion: str, energy: str, budget: str, weather: str) -> float:
    m = 1.0
    if companion and companion not in a.companion:
        m *= 0.65
    if energy and energy in _ENERGY and _ENERGY[a.energy] > _ENERGY[energy] + 0:
        # user wants calmer than this activity → soft down-weight
        if _ENERGY[a.energy] - _ENERGY[energy] >= 1:
            m *= 0.7
    if budget and budget in _COST and _COST[a.cost] > _COST[budget]:
        m *= 0.6
    # Weather: rain/cold → favor indoor, penalize outdoor.
    w = weather.lower()
    if any(k in w for k in ("rain", "storm", "snow", "wet", "雨")):
        m *= 1.15 if a.indoor else 0.5
    return m


def _cold_start_base(a: Activity) -> float:
    """Default appeal when there is no taste and no ask.

    Prefer approachable, low-friction weekend ideas (chill / mid energy, $,
    half-day) over adrenaline / $$$ / overnight — so catalog order alone
    doesn't dump skydiving + paragliding on every cold-start user."""
    energy_w = {"low": 1.0, "medium": 0.92, "high": 0.55}.get(a.energy, 0.8)
    cost_w = {"$": 1.0, "$$": 0.9, "$$$": 0.5}.get(a.cost, 0.8)
    if a.duration_h <= 3.5:
        dur_w = 1.0
    elif a.duration_h <= 5.0:
        dur_w = 0.88
    else:
        dur_w = 0.55  # overnight / full-day projects

    tags = set(a.tags)
    chill_hits = len(tags & _CHILL_TAGS)
    thrill_hits = len(tags & _THRILL_TAGS)
    vibe_w = 1.0 + 0.04 * chill_hits
    if thrill_hits and chill_hits == 0:
        vibe_w *= 0.62
    elif thrill_hits:
        vibe_w *= 0.85

    return 0.55 * energy_w + 0.25 * cost_w + 0.15 * dur_w + 0.05 * vibe_w


def _bucket(a: Activity) -> str:
    tags = set(a.tags)
    if tags & _THRILL_TAGS:
        return "thrill"
    if tags & {"creative", "hands-on"} and a.indoor:
        return "creative"
    if tags & {"wellness", "quiet", "cozy"}:
        return "wellness"
    if tags & {"culture", "aesthetic"} and a.indoor:
        return "culture"
    if tags & {"social", "playful", "puzzle", "night", "entertainment", "music"}:
        return "social"
    if tags & {"food", "local"}:
        return "food"
    if not a.indoor:
        return "outdoor"
    return "other"


def _diversify(
    scored: list[tuple[float, Activity, bool]], k: int, *, max_per_bucket: int = 2
) -> list[tuple[float, Activity, bool]]:
    """Pick top-k with vibe variety so cold-start isn't five thrill clones."""
    picked: list[tuple[float, Activity, bool]] = []
    counts: dict[str, int] = {}
    leftovers: list[tuple[float, Activity, bool]] = []
    for item in scored:
        bucket = _bucket(item[1])
        if counts.get(bucket, 0) < max_per_bucket:
            picked.append(item)
            counts[bucket] = counts.get(bucket, 0) + 1
        else:
            leftovers.append(item)
        if len(picked) >= k:
            return picked
    for item in leftovers:
        if len(picked) >= k:
            break
        picked.append(item)
    return picked


def _reason(a: Activity, in_season: bool, by_taste: bool, zh: bool) -> str:
    if zh:
        bits = [a.blurb] if a.blurb else []
        bits.append(f"约 {a.duration_h:g} 小时")
        if in_season:
            bits.append("正当季")
        if by_taste:
            bits.append("按你的偏好挑的")
        return "；".join(bits) + "。"
    bits = [a.blurb] if a.blurb else []
    bits.append(f"~{a.duration_h:g}h")
    if in_season:
        bits.append("in season")
    if by_taste:
        bits.append("matches your taste")
    return "; ".join(bits) + "."


async def recommend_activities(
    db: Session | None,
    user: User | None,
    *,
    interests: str = "",
    companion: str = "",
    energy: str = "",
    budget: str = "",
    weather: str = "",
    language: str = "en",
    k: int = 8,
) -> list[ActivitySuggestion]:
    # Taste vector (who you are) + English-ified ask (what you feel like now).
    taste_vec = None
    if db is not None and user is not None:
        try:
            from app.services.taste_profile import build_taste_profile

            taste_vec = (await build_taste_profile(db, user)).vector
        except Exception:
            taste_vec = None

    en_query = ""
    if interests.strip():
        from app.services.discovery import _english_query

        en_query = await _english_query(interests)

    qvec = await embed_query(en_query or interests.strip()) if interests.strip() else None
    cold_start = qvec is None and taste_vec is None
    act_vecs = (
        await embed_texts([a.text() for a in ACTIVITIES])
        if not cold_start
        else None
    )

    zh = language.lower().startswith("zh")
    month = datetime.utcnow().month
    scored: list[tuple[float, Activity, bool]] = []
    for i, a in enumerate(ACTIVITIES):
        by_taste = False
        if act_vecs is not None:
            sim_q = _cosine(qvec, act_vecs[i]) if qvec is not None else None
            sim_t = _cosine(taste_vec, act_vecs[i]) if taste_vec is not None else None
            if sim_q is not None and sim_t is not None:
                base = 0.6 * sim_q + 0.4 * sim_t
            elif sim_t is not None:
                base, by_taste = sim_t, True
            else:
                base = sim_q or 0.0
        else:
            # Zero-signal cold start: approachable defaults, not catalog order.
            base = _cold_start_base(a)
        season = _season_mult(a, month)
        ctx = _context_mult(a, companion=companion, energy=energy, budget=budget, weather=weather)
        scored.append((base * season * ctx, a, by_taste))

    scored.sort(key=lambda t: t[0], reverse=True)
    # Always diversify a bit; cold start is stricter (max 2 per vibe bucket).
    top = _diversify(scored, k, max_per_bucket=2 if cold_start else 3)

    out: list[ActivitySuggestion] = []
    for score, a, by_taste in top:
        in_season = _season_mult(a, month) >= 1.0
        out.append(
            ActivitySuggestion(
                key=a.key,
                name=a.name_zh if zh else a.name_en,
                name_en=a.name_en,
                name_zh=a.name_zh,
                tags=list(a.tags),
                duration_h=a.duration_h,
                energy=a.energy,
                cost=a.cost,
                companion=list(a.companion),
                indoor=a.indoor,
                in_season=in_season,
                match_score=round(score, 3),
                blurb=a.blurb,
                reason=_reason(a, in_season, by_taste, zh),
            )
        )
    return out
