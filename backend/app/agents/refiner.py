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
from app.services.constraint_engine import find_candidates
from app.services.destinations import DESTINATIONS
from app.services.i18n import lang_name, tr
from app.services.llm import fetch_weather_note, generate_summary

Intent = str

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

    # No rule matched — use the user's own LLM if configured, else explain capabilities.
    ctx = f"Current plan: {it.destination}, {it.drive_time} drive. {it.summary}"
    history = "\n".join(f"{m.role}: {m.content}" for m in req.messages[-6:])
    prompt = (
        "You are a spontaneous North America travel assistant. Be concise and actionable.\n"
        f"{ctx}\n\nConversation:\n{history}\n\nReply to the latest user message.\n"
        f"Respond in {lang_name(lang)}. Keep place names in English."
    )
    reply = await generate_summary(prompt)
    if not reply:
        reply = tr("capabilities", lang)
    return ChatResponse(reply=reply, itinerary=it)
