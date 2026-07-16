from __future__ import annotations

from app.agents.planner import _build_itinerary
from app.models.schemas import (
    Activity,
    ChatRequest,
    ChatResponse,
    DayPlan,
    Itinerary,
    Location,
    PlanRequest,
)
from app.services.constraint_engine import ScoredDestination, find_candidates
from app.services.destinations import DESTINATIONS
from app.services.geo import estimate_drive_hours, format_duration, haversine_miles
from app.services.i18n import lang_name, tr
from app.services.llm import fetch_weather_note, generate_summary
from app.services.retrieval import retriever

# Fixed role/behaviour lives in the system message; the user prompt carries only
# the current plan, retrieved facts, and conversation turns.
_CHAT_SYSTEM = (
    "You are a spontaneous North America travel assistant. Be concise and "
    "actionable. Ground answers in the provided destination facts; do not invent "
    "places. Keep place names in English."
)

Intent = str

# Short aliases (EN + ZH) users are likely to type for each catalog destination.
_DEST_ALIASES: dict[str, tuple[str, ...]] = {
    "Yosemite National Park": ("yosemite", "优胜美地", "约塞米蒂"),
    "Muir Woods National Monument": ("muir", "缪尔", "红杉森林"),
    "Point Reyes National Seashore": ("point reyes", "reyes", "雷斯岬"),
    "Big Basin Redwoods State Park": ("big basin", "basin"),
    "Golden Gate Park & Lands End": ("golden gate", "lands end", "金门"),
    "Lake Tahoe — Emerald Bay": ("tahoe", "太浩", "emerald bay"),
    "Mount Tamalpais State Park": ("tamalpais", "mount tam", "塔玛佩斯"),
    "Pinnacles National Park": ("pinnacles", "品纳克斯"),
    "Portland — Forest Park & Pearl District": ("portland", "波特兰", "pearl district"),
    "Columbia River Gorge — Multnomah Falls": ("multnomah", "columbia", "哥伦比亚"),
    "Olympic National Park — Hurricane Ridge": ("olympic", "hurricane ridge", "奥林匹克"),
    "Mount Rainier — Paradise": ("rainier", "雷尼尔"),
}

_PLAN_INTENT = (
    "plan", "itinerary", "trip to", "go to", "take me to", "visit", "want to see",
    "计划", "规划", "行程", "安排", "想去", "带我去", "改成", "换成", "要去", "去",
)

_PREF_KEYWORDS: dict[str, tuple[str, ...]] = {
    "beach": ("beach", "海滩", "沙滩", "海边"),
    "forest": ("forest", "森林", "树林"),
    "hiking": ("hiking", "hike", "徒步", "爬山", "登山"),
    "city-walk": ("city walk", "citywalk", "城市漫步", "逛街", "逛逛"),
    "national-park": ("national park", "国家公园"),
}

_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    "closer": ("closer", "nearer", "shorter drive", "less driving", "not too far",
               "更近", "近一点", "近点", "近些", "短一点", "别太远", "太远", "远了"),
    "different": ("different", "another", "switch", "somewhere else", "other option",
                  "change destination", "换", "换一个", "换个", "别的", "其他", "其它"),
    "relaxed": ("relax", "slower", "slow", "chill", "easy", "less packed", "too much",
                "轻松", "慢", "悠闲", "少一点", "太满", "太赶", "休闲"),
    "busier": ("more", "add", "busy", "pack", "extra", "fuller",
               "多一点", "多点", "丰富", "再加", "充实", "更多"),
    "family": ("kid", "kids", "family", "child", "children",
               "孩子", "小孩", "家庭", "亲子", "老人"),
}


def _detect_intent(text: str) -> Intent | None:
    low = text.lower()
    for intent, words in _KEYWORDS.items():
        if any(w in low for w in words):
            return intent
    return None


def _dest_by_name(name: str):
    for d in DESTINATIONS:
        if d.name == name:
            return d
    return None


def _has_plan_intent(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in _PLAN_INTENT)


def _match_destination(text: str) -> str | None:
    low = text.lower()
    for name, aliases in _DEST_ALIASES.items():
        if any(a in low for a in aliases):
            return name
    return None


def _match_preferences(text: str) -> list[str]:
    low = text.lower()
    return [pref for pref, words in _PREF_KEYWORDS.items() if any(w in low for w in words)]


def _scored_from_dest(origin: Location, name: str) -> ScoredDestination | None:
    dest = _dest_by_name(name)
    if not dest:
        return None
    miles = haversine_miles(origin.lat, origin.lng, dest.lat, dest.lng)
    hours = estimate_drive_hours(miles)
    return ScoredDestination(
        destination=dest,
        distance_miles=round(miles, 1),
        drive_hours=round(hours, 2),
        drive_time=format_duration(hours),
        score=0.0,
    )


def _plan_request_from_itinerary(req: ChatRequest, it: Itinerary) -> PlanRequest:
    trip_type = "weekend" if len(it.days) > 1 else "day-trip"
    start = it.days[0].date
    end = it.days[-1].date if len(it.days) > 1 else None
    return PlanRequest(
        origin=req.origin or Location(lat=it.destination_lat, lng=it.destination_lng, label=""),
        trip_type=trip_type,
        start_date=start,
        end_date=end,
        max_drive_hours=8.0,
        max_flight_hours=3.0,
        preferences=req.preferences,
        allow_flight=trip_type == "weekend",
        language=req.language,
    )


async def _set_destination(req: ChatRequest, it: Itinerary, name: str) -> ChatResponse:
    lang = req.language
    plan_req = _plan_request_from_itinerary(req, it)
    scored = _scored_from_dest(plan_req.origin, name)
    if scored is None:
        return ChatResponse(reply=tr("no_other", lang), itinerary=it)

    weather = await fetch_weather_note(scored.destination.lat, scored.destination.lng, lang)
    alts = [c.destination.name for c in find_candidates(plan_req, limit=4) if c.destination.name != name][:2]
    summary = tr(
        "switch_summary",
        lang,
        name=scored.destination.name,
        highlight=scored.destination.highlight,
        time=scored.drive_time,
        origin=plan_req.origin.label or "your start",
    )
    new_it = _build_itinerary(plan_req, scored, alts, weather, summary)
    reply = tr(
        "set_destination_reply",
        lang,
        name=scored.destination.name,
        time=scored.drive_time,
        highlight=scored.destination.highlight,
    )
    return ChatResponse(reply=reply, itinerary=new_it)


async def _replan_preferences(req: ChatRequest, it: Itinerary, prefs: list[str]) -> ChatResponse:
    lang = req.language
    plan_req = _plan_request_from_itinerary(req, it)
    plan_req.preferences = prefs  # type: ignore[assignment]
    candidates = find_candidates(plan_req, limit=8)
    if not candidates:
        return ChatResponse(reply=tr("no_other", lang), itinerary=it)
    chosen = candidates[0]
    weather = await fetch_weather_note(chosen.destination.lat, chosen.destination.lng, lang)
    alts = [c.destination.name for c in candidates[1:3]]
    summary = tr(
        "switch_summary",
        lang,
        name=chosen.destination.name,
        highlight=chosen.destination.highlight,
        time=chosen.drive_time,
        origin=plan_req.origin.label or "your start",
    )
    new_it = _build_itinerary(plan_req, chosen, alts, weather, summary)
    reply = tr("replan_reply", lang, name=chosen.destination.name, time=chosen.drive_time)
    return ChatResponse(reply=reply, itinerary=new_it)


async def _switch_destination(req: ChatRequest, it: Itinerary, prefer: str) -> ChatResponse | None:
    lang = req.language
    plan_req = _plan_request_from_itinerary(req, it)
    candidates = [c for c in find_candidates(plan_req, limit=8) if c.destination.name != it.destination]
    if not candidates:
        return ChatResponse(reply=tr("no_other", lang), itinerary=it)

    if prefer == "closer":
        candidates.sort(key=lambda c: c.drive_hours)
    chosen = candidates[0]

    weather = await fetch_weather_note(chosen.destination.lat, chosen.destination.lng, lang)
    alts = [c.destination.name for c in candidates[1:3]]
    summary = tr(
        "switch_summary",
        lang,
        name=chosen.destination.name,
        highlight=chosen.destination.highlight,
        time=chosen.drive_time,
        origin=plan_req.origin.label or "your start",
    )
    new_it = _build_itinerary(plan_req, chosen, alts, weather, summary)
    reply_key = "closer_reply" if prefer == "closer" else "different_reply"
    reply = tr(
        reply_key,
        lang,
        name=chosen.destination.name,
        time=chosen.drive_time,
        highlight=chosen.destination.highlight,
    )
    return ChatResponse(reply=reply, itinerary=new_it)


def _relax(it: Itinerary, lang: str) -> ChatResponse:
    new_days: list[DayPlan] = []
    for day in it.days:
        acts = list(day.activities)
        if len(acts) > 2:
            acts = acts[:2]
        if acts:
            acts[0] = Activity(
                time="10:30", place=acts[0].place, duration=acts[0].duration, note=acts[0].note
            )
        new_days.append(DayPlan(date=day.date, activities=acts))
    new_it = it.model_copy(update={"days": new_days, "summary": tr("relaxed_summary", lang)})
    return ChatResponse(reply=tr("relaxed_reply", lang), itinerary=new_it)


def _busier(it: Itinerary, lang: str) -> ChatResponse:
    dest = _dest_by_name(it.destination)
    if not dest:
        return ChatResponse(reply=tr("busier_fail", lang), itinerary=it)

    full_rows = list(dest.day_activities) + list(dest.weekend_extra)
    new_days: list[DayPlan] = []
    for day in it.days:
        rows = full_rows if len(it.days) > 1 else list(dest.day_activities)
        acts = [Activity(time=t, place=p, duration=d, note=n) for t, p, d, n in rows]
        new_days.append(DayPlan(date=day.date, activities=acts))
    new_it = it.model_copy(update={"days": new_days, "summary": tr("busier_summary", lang)})
    return ChatResponse(reply=tr("busier_reply", lang, name=it.destination), itinerary=new_it)


async def _family(req: ChatRequest, it: Itinerary) -> ChatResponse:
    lang = req.language
    plan_req = _plan_request_from_itinerary(req, it)
    easy_tags = {"city-walk", "forest", "beach"}
    candidates = find_candidates(plan_req, limit=8)
    easy = [c for c in candidates if easy_tags & {t.value for t in c.destination.tags}]
    if easy and easy[0].destination.name != it.destination:
        chosen = easy[0]
        weather = await fetch_weather_note(chosen.destination.lat, chosen.destination.lng, lang)
        alts = [c.destination.name for c in easy[1:3]]
        summary = tr(
            "family_summary", lang, name=chosen.destination.name, highlight=chosen.destination.highlight
        )
        new_it = _build_itinerary(plan_req, chosen, alts, weather, summary)
        relaxed = _relax(new_it, lang).itinerary
        return ChatResponse(reply=tr("family_reply", lang, name=chosen.destination.name), itinerary=relaxed)
    return _relax(it, lang)


async def refine(req: ChatRequest) -> ChatResponse:
    lang = req.language
    user_msgs = [m for m in req.messages if m.role == "user"]
    if not user_msgs:
        return ChatResponse(reply=tr("tell_me", lang), itinerary=req.current_itinerary)

    text = user_msgs[-1].content
    it = req.current_itinerary

    if it is None:
        return ChatResponse(reply=tr("no_plan", lang), itinerary=None)

    # Explicit "I want a plan for X" — rebuild the itinerary in real time.
    named = _match_destination(text)
    if named and (_has_plan_intent(text) or named != it.destination):
        return await _set_destination(req, it, named)

    prefs = _match_preferences(text)
    if prefs and _has_plan_intent(text):
        return await _replan_preferences(req, it, prefs)

    intent = _detect_intent(text)

    if intent == "closer":
        return await _switch_destination(req, it, prefer="closer") or _relax(it, lang)
    if intent == "different":
        return await _switch_destination(req, it, prefer="different") or _relax(it, lang)
    if intent == "relaxed":
        return _relax(it, lang)
    if intent == "busier":
        return _busier(it, lang)
    if intent == "family":
        return await _family(req, it)

    # No rule matched — RAG: retrieve relevant destinations, then let the LLM answer
    # grounded in those facts (falls back to a capabilities message with no LLM key).
    retrieved = await retriever.retrieve(text, k=3)
    knowledge = "\n".join(f"- {doc.text}" for doc, _ in retrieved) or "- (no matches)"
    ctx = f"Current plan: {it.destination}, {it.drive_time} drive. {it.summary}"
    history = "\n".join(f"{m.role}: {m.content}" for m in req.messages[-6:])
    prompt = (
        f"{ctx}\n\nDestination facts:\n{knowledge}\n\n"
        f"Conversation:\n{history}\n\nReply to the latest user message. "
        f"Respond in {lang_name(lang)}."
    )
    reply = await generate_summary(prompt, system=_CHAT_SYSTEM)
    if not reply:
        reply = tr("capabilities", lang)
    return ChatResponse(reply=reply, itinerary=it)
