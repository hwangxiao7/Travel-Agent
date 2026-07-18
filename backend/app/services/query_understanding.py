from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import asdict, dataclass, field

from app.models.schemas import Preference

# Lightweight, deterministic NLP for travel queries (EN + ZH).
# Optional LLM rewrite can refine later; rules keep zero-key reliability.


@dataclass
class TravelIntent:
    raw_query: str
    normalized_query: str = ""
    rewritten_query: str = ""
    trip_type: str | None = None  # day-trip | weekend
    max_drive_hours: float | None = None
    max_flight_hours: float | None = None
    allow_flight: bool | None = None
    activities: list[str] = field(default_factory=list)
    scenery: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)  # Preference enum values
    # Open-vocabulary content terms from the free-text query (not a closed specialty enum).
    focus_terms: list[str] = field(default_factory=list)
    season: str | None = None
    budget: str | None = None  # low | mid | high
    pace: str | None = None  # easy | moderate | strenuous
    constraints: list[str] = field(default_factory=list)
    negative_preferences: list[str] = field(default_factory=list)
    # Local-discovery framing (design doc §1-2, §8): not just "travel destinations".
    social_context: str | None = None  # solo | couple | friends | family
    energy_level: str | None = None  # low | medium | high
    mood: list[str] = field(default_factory=list)  # relax | adventure | romantic | social | explore | fun
    time_window: str | None = None  # tonight | today | evening | weekend

    def to_dict(self) -> dict:
        return asdict(self)


_HOUR_RE = re.compile(
    r"(?P<n>\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours|小时|個小時|个小时)",
    re.I,
)
_DRIVE_HINT = re.compile(r"(drive|car|车程|开车|自驾|within|以内|内)", re.I)
_FLIGHT_HINT = re.compile(r"(flight|fly|飞|航班|飞行)", re.I)

_ACTIVITY_MAP: list[tuple[re.Pattern[str], str, str | None]] = [
    (re.compile(r"hik(e|ing)|徒步|远足|登山", re.I), "hiking", Preference.HIKING.value),
    (re.compile(r"beach|swim|海岸|海滩|沙滩", re.I), "beach", Preference.BEACH.value),
    (re.compile(r"city\s*walk|urban|city|城市|漫步|逛街", re.I), "city-walk", Preference.CITY_WALK.value),
    (re.compile(r"national\s*park|国家公园", re.I), "national-park", Preference.NATIONAL_PARK.value),
    (re.compile(r"forest|woods|redwood|森林|红杉", re.I), "forest", Preference.FOREST.value),
    (re.compile(r"aurora|northern\s*lights|极光", re.I), "aurora", None),
    (re.compile(r"whale\s*watch(?:ing)?|whale|orcas?|观鲸|看鲸鱼|鲸鱼|虎鲸", re.I), "whale-watching", None),
    (
        re.compile(
            r"真人\s*CS|真人CS|paintball|airsoft|laser\s*tag|漆弹|彩弹|野战|生存游戏",
            re.I,
        ),
        "paintball",
        None,
    ),
    (
        re.compile(
            r"snorkel(?:ing)?|scuba|diving|浮潜|潜水|snorkeling",
            re.I,
        ),
        "snorkeling",
        None,
    ),
    (re.compile(r"camp(ing)?|露营", re.I), "camping", None),
    (re.compile(r"photo|摄影|拍照", re.I), "photography", None),
    (re.compile(r"food|coffee|cafe|吃|咖啡|美食", re.I), "food", None),
]

_SCENERY_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"aurora|northern\s*lights|极光", re.I), "aurora"),
    (re.compile(r"whale|orcas?|观鲸|鲸鱼", re.I), "whale"),
    (re.compile(r"snorkel|scuba|浮潜|潜水", re.I), "underwater"),
    (re.compile(r"waterfall|falls|瀑布", re.I), "waterfall"),
    (re.compile(r"lake|湖泊|湖", re.I), "lake"),
    (re.compile(r"mountain|peak|山|峰", re.I), "mountain"),
    (re.compile(r"coast|ocean|sea|海边|海岸", re.I), "coast"),
    (re.compile(r"desert|沙漠", re.I), "desert"),
    (re.compile(r"canyon|峡谷", re.I), "canyon"),
    (re.compile(r"view|viewpoint|观景|风景", re.I), "viewpoint"),
    (re.compile(r"quiet|peaceful|安静|清静", re.I), "quiet"),
]

# --- Local-discovery framing maps (design doc §1-2, §8) ---
_SOCIAL_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bsolo\b|alone|by myself|one person|独自|一个人|自己一个", re.I), "solo"),
    (re.compile(r"\bdate\b|romantic|my partner|girlfriend|boyfriend|couple|约会|情侣|对象|两个人", re.I), "couple"),
    (re.compile(r"friends|buddies|group|hang ?out|朋友|一群|聚会", re.I), "friends"),
    (re.compile(r"family|kids|children|parents|家人|孩子|带娃|一家", re.I), "family"),
]
_ENERGY_LOW = re.compile(
    r"tired|exhausted|relax(ing)?|chill|low.?key|unwind|lazy|easy going|"
    r"累|疲惫|放松|休闲|懒|轻松",
    re.I,
)
_ENERGY_HIGH = re.compile(
    r"adventur|energetic|active|thrill|pumped|intense|explore a lot|"
    r"刺激|冒险|活力|挑战|嗨",
    re.I,
)
_MOOD_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"relax|chill|unwind|calm|de-?stress|放松|解压|静", re.I), "relax"),
    (re.compile(r"romantic|date|cozy|intimate|浪漫|约会|温馨", re.I), "romantic"),
    (re.compile(r"adventur|thrill|explore|discover|new|冒险|探索|新鲜", re.I), "adventure"),
    (re.compile(r"fun|exciting|lively|party|好玩|热闹|嗨", re.I), "fun"),
    (re.compile(r"social|meet people|friends|社交|认识", re.I), "social"),
]
_TIME_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"tonight|this evening|今晚|今天晚上", re.I), "tonight"),
    (re.compile(r"today|right now|this afternoon|今天|现在|下午", re.I), "today"),
    (re.compile(r"evening|dinner time|傍晚|晚上", re.I), "evening"),
    (re.compile(r"weekend|周末|礼拜六|星期六|星期天|礼拜天", re.I), "weekend"),
]

# Open-vocabulary specialties: not Preference enum tags; matched against corpus text.
# Add a row here + destination copy mentioning the keywords → retrieval works without UI chips.
_SPECIALTY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "aurora": ("aurora", "northern lights", "northern light", "auroral", "极光"),
    "whale-watching": (
        "whale",
        "whales",
        "whale watching",
        "whale-watching",
        "whale watch",
        "orca",
        "orcas",
        "观鲸",
        "鲸鱼",
    ),
    "paintball": (
        "paintball",
        "airsoft",
        "laser tag",
        "真人CS",
        "漆弹",
        "彩弹",
        "野战",
        "survival game",
        "tactical",
    ),
    "snorkeling": (
        "snorkel",
        "snorkeling",
        "scuba",
        "diving",
        "kelp",
        "reef",
        "浮潜",
        "潜水",
        "underwater",
    ),
    "camping": ("camp", "camping", "campground", "露营"),
    "photography": ("photo", "photography", "photogenic", "摄影"),
    "food": ("food", "cafe", "coffee", "restaurant", "美食", "咖啡"),
}

# Specialty trips that almost always need a flight from the lower 48 / coastal cities.
_AURORA_FLIGHT_HOURS = 7.0

# Preference enum values — UI chips. Specialty intents should outrank these when present.
_PREFERENCE_VALUES = {p.value for p in Preference}


def preference_match_score(dest_tags: set[str] | tuple[str, ...] | list[str], prefs: list[str]) -> float:
    """Equal-weight OR over preference chips.

    Matching *any one* selected preference scores ~1.0. Extra matches get only a
    tiny bonus — so city-walk alone ties national-park alone, and multi-tag parks
    no longer dominate when the user checks every chip.
    """
    if not prefs:
        return 1.0
    wanted = {p.value if hasattr(p, "value") else str(p) for p in prefs}
    tags = {t.value if hasattr(t, "value") else str(t) for t in dest_tags}
    overlap = len(tags & wanted)
    if overlap == 0:
        return 0.0
    return min(1.15, 1.0 + 0.05 * (overlap - 1))


_EN_STOP = {
    "the", "and", "for", "with", "from", "want", "wanna", "like", "love", "trip",
    "day", "weekend", "near", "nearby", "within", "hours", "hour", "drive", "flight",
    "please", "some", "something", "good", "great", "nice", "very", "really", "just",
    "into", "onto", "about", "this", "that", "have", "need", "looking", "find",
    "place", "places", "spot", "spots", "area", "around", "where", "can", "could",
}
_ZH_FILLER = re.compile(
    r"(我想要?|想要|想去|想|去玩|去看|突发奇想|能不能|可以吗?|可以|一下|一个|这个|那个|"
    r"比较|非常|真的|最好是?|附近|周边|地方|活动|玩法|体验|找个|找一?个|哪里|哪儿)",
)
_ZH_STOP_CHARS = set("的了吗呢吧啊呀嘛在和有能要我你他她它们")
_ZH_STOP_TERMS = {
    "找个", "找一", "可以", "附近", "周边", "地方", "活动", "玩法", "体验",
    "哪里", "哪儿", "什么", "怎么", "我们", "一个", "一下",
}


def extract_focus_terms(query: str) -> list[str]:
    """Detect whether free text has a content focus (not a closed activity enum).

    Terms are for intent/debug only — retrieval uses LLM rewrite + embeddings,
    not substring matching against these tokens.
    """
    terms: list[str] = []
    for w in re.findall(r"[a-zA-Z]{3,}", query.lower()):
        if w not in _EN_STOP and w not in terms:
            terms.append(w)

    zh = _ZH_FILLER.sub(" ", query)
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", zh):
        cleaned = "".join(ch for ch in chunk if ch not in _ZH_STOP_CHARS)
        if cleaned in _ZH_STOP_TERMS:
            continue
        if len(cleaned) >= 2 and cleaned not in terms and cleaned not in _ZH_STOP_TERMS:
            terms.append(cleaned)
        elif (
            len(chunk) >= 2
            and chunk not in terms
            and chunk not in _ZH_STOP_TERMS
            and chunk not in ("我们", "什么", "怎么")
        ):
            terms.append(chunk)

    return [
        t
        for t in terms
        if t not in _PREFERENCE_VALUES
        and t.replace("-", "") not in _PREFERENCE_VALUES
        and t not in _ZH_STOP_TERMS
    ]


def has_focus_query(intent: TravelIntent) -> bool:
    return bool(intent.focus_terms)


def focus_match_score(text: str, intent: TravelIntent) -> float:
    """Legacy substring overlap — soft signal only. Do not use as retrieval gate."""
    terms = intent.focus_terms
    if not terms:
        return 0.0
    blob = text.lower()
    content = [t for t in terms if len(t) >= 2 and t not in _ZH_STOP_TERMS]
    if not content:
        content = terms
    hits = sum(1 for t in content if t.lower() in blob)
    return hits / len(content) if hits else 0.0


def doc_matches_focus(text: str, intent: TravelIntent) -> bool:
    return focus_match_score(text, intent) > 0


def specialty_intents(intent: TravelIntent) -> list[str]:
    """Optional known labels for routing/explain — NOT required for retrieval."""
    out: list[str] = []
    for a in intent.activities:
        if a in _SPECIALTY_KEYWORDS and a not in out:
            out.append(a)
    if "whale" in intent.scenery and "whale-watching" not in out:
        out.append("whale-watching")
    if "aurora" in intent.scenery and "aurora" not in out:
        out.append("aurora")
    if "underwater" in intent.scenery and "snorkeling" not in out:
        out.append("snorkeling")
    return out


def specialty_match_keywords(intent: TravelIntent) -> tuple[str, ...]:
    keys: list[str] = []
    for s in specialty_intents(intent):
        keys.extend(_SPECIALTY_KEYWORDS.get(s, ()))
    # Always include open-vocab focus terms.
    keys.extend(intent.focus_terms)
    return tuple(dict.fromkeys(keys))


def doc_matches_specialty(text: str, intent: TravelIntent) -> bool:
    """Back-compat name: true if open-vocab focus OR known specialty keywords hit."""
    return doc_matches_focus(text, intent)

_SEASON_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"spring|春天|春季", re.I), "spring"),
    (re.compile(r"summer|夏天|夏季", re.I), "summer"),
    (re.compile(r"fall|autumn|秋天|秋季", re.I), "fall"),
    (re.compile(r"winter|冬天|冬季", re.I), "winter"),
]

_BUDGET_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"cheap|budget|便宜|穷游|省钱", re.I), "low"),
    (re.compile(r"luxury|fancy|豪华|奢华", re.I), "high"),
    (re.compile(r"mid[- ]?range|适中|中等", re.I), "mid"),
]

_PACE_EASY = re.compile(
    r"easy|relax(ed|ing)?|chill|gentle|不要太累|轻松|悠闲|休闲|不累|轻松点",
    re.I,
)
_PACE_HARD = re.compile(r"strenuous|challenging|intense|hardcore|高强度|挑战|累一点", re.I)

_NEGATIVE_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?:don'?t|do not|no|avoid|不要|别|别太|不想).{0,12}(crowd|人多|拥挤)", re.I), "crowded"),
    (re.compile(r"(?:don'?t|do not|no|avoid|不要|别|别太|不想).{0,12}(strenuous|hard|累|辛苦|高强度)", re.I), "strenuous"),
    (re.compile(r"(?:don'?t|do not|no|avoid|不要|别).{0,12}(hot|热|晒)", re.I), "hot"),
    (re.compile(r"(?:don'?t|do not|no|avoid|不要|别).{0,12}(far|远)", re.I), "far"),
    (re.compile(r"(?:don'?t|do not|no|avoid|不要|别).{0,12}(kid|child|孩子|带娃)", re.I), "family"),
    (re.compile(r"不要太累|别太累|轻松点|轻松一点", re.I), "strenuous"),
]

_WEEKEND = re.compile(r"weekend|overnight|两天|周末|过夜", re.I)
_DAYTRIP = re.compile(r"day[- ]?trip|一日|当天回|当天", re.I)


def normalize_query(text: str) -> str:
    q = text.strip()
    q = re.sub(r"\s+", " ", q)
    return q


def extract_intent(query: str) -> TravelIntent:
    raw = query.strip()
    norm = normalize_query(raw)
    intent = TravelIntent(raw_query=raw, normalized_query=norm)

    # Duration / drive / flight hours
    for m in _HOUR_RE.finditer(norm):
        hours = float(m.group("n"))
        window = norm[max(0, m.start() - 24) : m.end() + 24]
        if _FLIGHT_HINT.search(window) and not _DRIVE_HINT.search(window):
            intent.max_flight_hours = hours
            intent.allow_flight = True
        else:
            intent.max_drive_hours = hours

    if _WEEKEND.search(norm):
        intent.trip_type = "weekend"
    elif _DAYTRIP.search(norm):
        intent.trip_type = "day-trip"

    if _FLIGHT_HINT.search(norm) and intent.allow_flight is None:
        intent.allow_flight = True

    for pat, act, pref in _ACTIVITY_MAP:
        if pat.search(norm):
            if act not in intent.activities:
                intent.activities.append(act)
            if pref and pref not in intent.preferences:
                intent.preferences.append(pref)

    for pat, scene in _SCENERY_MAP:
        if pat.search(norm) and scene not in intent.scenery:
            intent.scenery.append(scene)

    for pat, season in _SEASON_MAP:
        if pat.search(norm):
            intent.season = season
            break

    for pat, budget in _BUDGET_MAP:
        if pat.search(norm):
            intent.budget = budget
            break

    # --- Local-discovery framing ---
    for pat, social in _SOCIAL_MAP:
        if pat.search(norm):
            intent.social_context = social
            break
    if _ENERGY_LOW.search(norm):
        intent.energy_level = "low"
    elif _ENERGY_HIGH.search(norm):
        intent.energy_level = "high"
    for pat, mood in _MOOD_MAP:
        if pat.search(norm) and mood not in intent.mood:
            intent.mood.append(mood)
    for pat, tw in _TIME_MAP:
        if pat.search(norm):
            intent.time_window = tw
            break

    if _PACE_EASY.search(norm):
        intent.pace = "easy"
    elif _PACE_HARD.search(norm):
        intent.pace = "strenuous"
    elif intent.energy_level == "low":
        intent.pace = "easy"  # tired/relaxed → easy pace
    elif intent.energy_level == "high":
        intent.pace = "strenuous"
    else:
        intent.pace = "moderate" if intent.activities else None

    for pat, neg in _NEGATIVE_MAP:
        if pat.search(norm) and neg not in intent.negative_preferences:
            intent.negative_preferences.append(neg)

    if intent.pace == "easy" and "strenuous" not in intent.negative_preferences:
        intent.negative_preferences.append("strenuous")

    # Aurora / northern lights → high-latitude fly trip (not a Bay Area day drive).
    if "aurora" in intent.scenery or "aurora" in intent.activities:
        intent.allow_flight = True
        if intent.max_flight_hours is None or intent.max_flight_hours < _AURORA_FLIGHT_HOURS:
            intent.max_flight_hours = _AURORA_FLIGHT_HOURS
        if intent.season is None:
            intent.season = "winter"
        if intent.trip_type is None:
            intent.trip_type = "weekend"
        intent.constraints.append("requires_aurora_latitude")

    # Open-vocab focus terms — primary signal for free-text search (not a closed enum).
    intent.focus_terms = extract_focus_terms(norm)
    if intent.focus_terms:
        intent.constraints.append("focus=" + ",".join(intent.focus_terms[:6]))

    if intent.max_drive_hours is not None:
        intent.constraints.append(f"max_drive_hours<={intent.max_drive_hours}")
    if intent.max_flight_hours is not None:
        intent.constraints.append(f"max_flight_hours<={intent.max_flight_hours}")
    if intent.pace:
        intent.constraints.append(f"pace={intent.pace}")
    for s in intent.scenery:
        intent.constraints.append(f"scenery={s}")
    if intent.social_context:
        intent.constraints.append(f"social={intent.social_context}")
    if intent.energy_level:
        intent.constraints.append(f"energy={intent.energy_level}")
    for m in intent.mood:
        intent.constraints.append(f"mood={m}")
    if intent.time_window:
        intent.constraints.append(f"time={intent.time_window}")

    intent.rewritten_query = rewrite_query(intent)
    return intent


# Any-language -> English activity phrasing. Two contracts share one core:
#   strict=True  -> tight 2-5 word noun phrase for POI / embedding retrieval
#   strict=False -> looser concrete phrase for open-ended "surprise me" discovery
_PHRASE_SYSTEM_STRICT = (
    "Rewrite a travel activity request as a short English noun phrase (2-5 "
    "words) naming the activity only. Examples: surfing, escape room, axe "
    "throwing, whale watching, hot springs. No politeness, no 'near "
    "me/nearby/please', no place names unless the user named one, no full "
    "sentences. Reply with ONLY the English phrase."
)
_PHRASE_SYSTEM_LOOSE = (
    "Translate/normalize the user's interests into a short, concrete English "
    "phrase describing the activity or experience they want (open vocabulary). "
    "Return only the phrase, nothing else."
)

# In-process LRU for LLM phrase normalization (strict + loose share one store).
_PHRASE_CACHE: OrderedDict[tuple[str, bool], str] = OrderedDict()
_PHRASE_CACHE_MAX = 512


def _phrase_cache_key(text: str, strict: bool) -> tuple[str, bool]:
    return (normalize_query(text).lower(), strict)


def _phrase_cache_get(key: tuple[str, bool]) -> str | None:
    if key not in _PHRASE_CACHE:
        return None
    _PHRASE_CACHE.move_to_end(key)
    return _PHRASE_CACHE[key]


def _phrase_cache_set(key: tuple[str, bool], value: str) -> None:
    _PHRASE_CACHE[key] = value
    _PHRASE_CACHE.move_to_end(key)
    while len(_PHRASE_CACHE) > _PHRASE_CACHE_MAX:
        _PHRASE_CACHE.popitem(last=False)


def rules_cover_activity(intent: TravelIntent) -> bool:
    """True when rule extraction already identified a known activity/specialty."""
    if intent.activities:
        return True
    return bool(specialty_intents(intent))


def needs_llm_activity_phrase(intent: TravelIntent) -> bool:
    """True when open-vocab focus remains after rules — the only case for LLM."""
    return has_focus_query(intent) and not rules_cover_activity(intent)


def phrase_from_rules(intent: TravelIntent) -> str:
    """Derive an English activity phrase from rule extraction (0 LLM tokens)."""
    if intent.activities:
        return intent.activities[0].replace("-", " ")
    specs = specialty_intents(intent)
    if specs:
        return specs[0].replace("-", " ")
    return ""


async def _llm_activity_phrase_uncached(text: str, *, strict: bool) -> str:
    """Call the LLM to normalize activity text (no cache)."""
    from app.services.llm import generate_summary

    q = (text or "").strip()
    if not q:
        return ""
    system = _PHRASE_SYSTEM_STRICT if strict else _PHRASE_SYSTEM_LOOSE
    raw = (
        await generate_summary(f"Request: {q}", system=system, temperature=0.2) or ""
    ).strip().strip('"').strip("'")
    if not strict:
        return raw[:120]
    if not raw or len(raw) > 60 or "\n" in raw:
        return ""
    low = raw.lower()
    if any(x in low for x in ("sorry", "cannot", "i ", "as an", "as a")):
        return ""
    cleaned = re.sub(
        r"\b(please|near me|nearby|around here|in the area)\b",
        " ",
        raw,
        flags=re.I,
    )
    cleaned = cleaned.replace("_", " ").replace("*", " ")
    cleaned = " ".join(cleaned.split()).strip(" .,!")
    return cleaned or raw


async def english_activity_phrase(text: str, *, strict: bool = True) -> str:
    """Open-vocab: rewrite any-language activity text into an English phrase.

    Shared by POI/embedding retrieval (strict) and discovery (loose). LRU-cached
    by normalized text + strict flag. Best-effort → "" on failure.
    """
    q = (text or "").strip()
    if not q:
        return ""
    key = _phrase_cache_key(q, strict)
    hit = _phrase_cache_get(key)
    if hit is not None:
        from app.observability import record_cache_hit

        record_cache_hit()
        return hit
    from app.observability import record_cache_miss

    record_cache_miss()
    result = await _llm_activity_phrase_uncached(q, strict=strict)
    _phrase_cache_set(key, result)
    return result


async def resolve_activity_phrase(
    query: str,
    intent: TravelIntent,
    *,
    strict: bool = True,
) -> str:
    """Resolve an English activity phrase with minimal LLM use.

    When rules already cover the activity (strict mode), returns phrase_from_rules
    with 0 tokens. Otherwise uses the LRU-backed english_activity_phrase path.
    """
    if strict and not needs_llm_activity_phrase(intent):
        return phrase_from_rules(intent)
    return await english_activity_phrase(query, strict=strict)


async def llm_activity_phrase(query: str, intent: TravelIntent | None = None) -> str:
    """Strict activity phrase for embedding retrieval and POI search."""
    if intent is None:
        intent = extract_intent(query)
    return await resolve_activity_phrase(query, intent, strict=True)


def rewrite_query(
    intent: TravelIntent,
    profile_text: str = "",
    activity_phrase: str = "",
) -> str:
    """Expand a short NL query into a retrieval-friendly query.

    Prefer an LLM English activity phrase (open-vocab) over raw multilingual tokens.
    """
    parts: list[str] = []
    phrase = (activity_phrase or "").strip()
    if phrase:
        parts.append(phrase)
    elif intent.normalized_query:
        parts.append(intent.normalized_query)
    if intent.activities:
        parts.append("activities: " + ", ".join(intent.activities))
    if intent.scenery:
        parts.append("scenery: " + ", ".join(intent.scenery))
    if intent.preferences:
        # Free-text focus dominates; UI chips are soft hints.
        if intent.focus_terms:
            parts.append(
                "optional soft tags: " + ", ".join(p.replace("-", " ") for p in intent.preferences)
            )
        else:
            parts.append("tags: " + ", ".join(p.replace("-", " ") for p in intent.preferences))
    if intent.pace:
        parts.append(f"pace: {intent.pace}")
    if intent.mood:
        parts.append("mood: " + ", ".join(intent.mood))
    if intent.energy_level:
        parts.append(f"energy: {intent.energy_level}")
    if intent.social_context:
        parts.append(f"company: {intent.social_context}")
    if intent.season:
        parts.append(f"season: {intent.season}")
    if intent.negative_preferences:
        parts.append("avoid: " + ", ".join(intent.negative_preferences))
    if profile_text and "none yet" not in profile_text.lower():
        parts.append("traveler likes: " + profile_text[:280])
    rewritten = ". ".join(parts)
    intent.rewritten_query = rewritten
    return rewritten


def apply_intent_to_request_fields(intent: TravelIntent, req) -> None:
    """Mutate a SearchRequest-like object with extracted constraints when useful."""
    if intent.max_drive_hours is not None:
        req.max_drive_hours = intent.max_drive_hours
    if intent.max_flight_hours is not None:
        req.max_flight_hours = intent.max_flight_hours
        req.allow_flight = True
    if intent.allow_flight:
        req.allow_flight = True
    if intent.trip_type:
        req.trip_type = intent.trip_type
    if intent.preferences:
        from app.models.schemas import Preference as Pref

        existing = {p.value if hasattr(p, "value") else str(p) for p in req.preferences}
        for p in intent.preferences:
            if p not in existing:
                try:
                    req.preferences.append(Pref(p))
                except ValueError:
                    pass
