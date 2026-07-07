from __future__ import annotations

from datetime import date, timedelta

from app.models.schemas import Activity, DayPlan, Itinerary, PlanRequest, Preference
from app.services.constraint_engine import ScoredDestination, find_candidates
from app.services.i18n import lang_name, pack, tr
from app.services.llm import fetch_weather_note, generate_summary


def _packing_tips(prefs: list[Preference], trip_type: str, lang: str) -> list[str]:
    keys = ["water", "snacks", "charger"]
    tags = set(prefs)
    if Preference.HIKING in tags or Preference.NATIONAL_PARK in tags:
        keys.extend(["trail_shoes", "rain_layer", "sunscreen"])
    if Preference.BEACH in tags:
        keys.append("sandals")
    if trip_type == "weekend":
        keys.extend(["overnight", "toiletries", "warm_layer"])
    return [pack(k, lang) for k in keys]


def _activities_from_dest(scored: ScoredDestination, day_index: int) -> list[Activity]:
    dest = scored.destination
    rows = list(dest.day_activities)
    if day_index == 1 and dest.weekend_extra:
        rows.extend(dest.weekend_extra)
    return [Activity(time=t, place=p, duration=d, note=n) for t, p, d, n in rows]


def _build_itinerary(
    request: PlanRequest,
    scored: ScoredDestination,
    alternatives: list[str],
    weather_note: str,
    summary: str,
) -> Itinerary:
    start = date.fromisoformat(request.start_date)
    days: list[DayPlan] = []

    if request.trip_type == "weekend":
        end = date.fromisoformat(request.end_date or (start + timedelta(days=1)).isoformat())
        day_count = (end - start).days + 1
        day_count = min(max(day_count, 2), 2)
        for i in range(day_count):
            d = start + timedelta(days=i)
            days.append(DayPlan(date=d.isoformat(), activities=_activities_from_dest(scored, i)))
    else:
        days.append(DayPlan(date=start.isoformat(), activities=_activities_from_dest(scored, 0)))

    return Itinerary(
        destination=scored.destination.name,
        destination_lat=scored.destination.lat,
        destination_lng=scored.destination.lng,
        drive_time=scored.drive_time,
        drive_hours=scored.drive_hours,
        days=days,
        alternatives=alternatives,
        packing_tips=_packing_tips(request.preferences, request.trip_type, request.language),
        weather_note=weather_note,
        summary=summary,
    )


async def create_plan(request: PlanRequest) -> tuple[Itinerary, list[dict]]:
    candidates = find_candidates(request)
    if not candidates:
        raise ValueError(
            "No destinations match your drive-time limit. Try increasing max drive hours or broadening preferences."
        )

    top = candidates[0]
    alts = [c.destination.name for c in candidates[1:3]]
    weather = await fetch_weather_note(top.destination.lat, top.destination.lng, request.language)

    summary_prompt = (
        f"Write 2-3 sentences for a spontaneous trip plan.\n"
        f"Origin: {request.origin.label or 'user location'}\n"
        f"Destination: {top.destination.name} ({top.destination.highlight})\n"
        f"Drive: {top.drive_time}\n"
        f"Trip type: {request.trip_type}\n"
        f"Preferences: {', '.join(p.value for p in request.preferences) or 'general outdoor'}\n"
        f"Weather: {weather}\n"
        f"Tone: enthusiastic but practical.\n"
        f"Respond in {lang_name(request.language)}. Keep place names in English."
    )
    summary = await generate_summary(summary_prompt)
    if not summary:
        summary = tr(
            "summary_fallback",
            request.language,
            name=top.destination.name,
            highlight=top.destination.highlight,
            time=top.drive_time,
        )

    itinerary = _build_itinerary(request, top, alts, weather, summary)
    candidate_payload = [
        {
            "name": c.destination.name,
            "lat": c.destination.lat,
            "lng": c.destination.lng,
            "drive_time": c.drive_time,
            "drive_hours": c.drive_hours,
            "score": round(c.score, 2),
            "highlight": c.destination.highlight,
        }
        for c in candidates
    ]
    return itinerary, candidate_payload
