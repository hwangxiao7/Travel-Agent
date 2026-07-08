from __future__ import annotations

import asyncio
from datetime import date, timedelta

from app.models.schemas import (
    Activity,
    DayPlan,
    Event,
    FlyPlanRequest,
    Itinerary,
    Place,
    PlanRequest,
    Preference,
    SelectRequest,
)
from app.services.airports import airport_by_iata, nearest_airport
from app.services.constraint_engine import ScoredDestination, find_candidates
from app.services.destinations import DESTINATIONS
from app.services.events import fetch_events
from app.services.fly_destinations import FLY_DESTINATIONS
from app.services.flights import estimate_flight
from app.services.geo import estimate_drive_hours, format_duration, haversine_miles
from app.services.i18n import lang_name, pack, tr
from app.services.llm import fetch_weather_note, generate_summary
from app.services.places import fetch_nearby_places


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


async def _local_highlights(
    lat: float, lng: float, start_date: str
) -> tuple[list[Place], list[Place], list[Event]]:
    """Fetch nearby food + fun (OSM) and events (Ticketmaster) concurrently.

    Each source is best-effort and degrades to empty on failure/no key."""
    (food, fun), events = await asyncio.gather(
        fetch_nearby_places(lat, lng),
        fetch_events(lat, lng, start_date),
    )
    return food, fun, events


def _build_itinerary(
    request: PlanRequest,
    scored: ScoredDestination,
    alternatives: list[str],
    weather_note: str,
    summary: str,
    nearby_food: list[Place] | None = None,
    nearby_fun: list[Place] | None = None,
    events: list[Event] | None = None,
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
        nearby_food=nearby_food or [],
        nearby_fun=nearby_fun or [],
        events=events or [],
    )


async def create_plan(request: PlanRequest) -> tuple[Itinerary, list[dict]]:
    candidates = find_candidates(request)
    if not candidates:
        raise ValueError(
            "No destinations match your drive-time limit. Try increasing max drive hours or broadening preferences."
        )

    top = candidates[0]
    alts = [c.destination.name for c in candidates[1:3]]
    weather, (food, fun, events) = await asyncio.gather(
        fetch_weather_note(top.destination.lat, top.destination.lng, request.language),
        _local_highlights(top.destination.lat, top.destination.lng, request.start_date),
    )

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

    itinerary = _build_itinerary(request, top, alts, weather, summary, food, fun, events)
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


async def plan_for_destination(req: SelectRequest) -> Itinerary:
    dest = next((d for d in DESTINATIONS if d.name == req.destination_name), None)
    if dest is None:
        raise ValueError(f"Unknown destination: {req.destination_name}")

    miles = haversine_miles(req.origin.lat, req.origin.lng, dest.lat, dest.lng)
    hours = estimate_drive_hours(miles)
    scored = ScoredDestination(
        destination=dest,
        distance_miles=round(miles, 1),
        drive_hours=round(hours, 2),
        drive_time=format_duration(hours),
        score=0.0,
    )

    plan_req = PlanRequest(
        origin=req.origin,
        trip_type=req.trip_type,
        start_date=req.start_date,
        end_date=req.end_date,
        max_drive_hours=8.0,
        max_flight_hours=3.0,
        preferences=req.preferences,
        allow_flight=req.trip_type == "weekend",
        language=req.language,
    )
    alts = [c.destination.name for c in find_candidates(plan_req, limit=4) if c.destination.name != dest.name][:2]
    weather, (food, fun, events) = await asyncio.gather(
        fetch_weather_note(dest.lat, dest.lng, req.language),
        _local_highlights(dest.lat, dest.lng, req.start_date),
    )

    summary_prompt = (
        f"Write 2-3 sentences for a spontaneous trip plan.\n"
        f"Origin: {req.origin.label or 'user location'}\n"
        f"Destination: {dest.name} ({dest.highlight})\n"
        f"Drive: {scored.drive_time}\n"
        f"Trip type: {req.trip_type}\n"
        f"Weather: {weather}\n"
        f"Tone: enthusiastic but practical.\n"
        f"Respond in {lang_name(req.language)}. Keep place names in English."
    )
    summary = await generate_summary(summary_prompt)
    if not summary:
        summary = tr(
            "summary_fallback",
            req.language,
            name=dest.name,
            highlight=dest.highlight,
            time=scored.drive_time,
        )

    return _build_itinerary(plan_req, scored, alts, weather, summary, food, fun, events)


async def plan_for_fly_destination(req: FlyPlanRequest) -> Itinerary:
    dest = next((d for d in FLY_DESTINATIONS if d.name == req.destination_name), None)
    if dest is None:
        raise ValueError(f"Unknown fly destination: {req.destination_name}")

    origin_ap = nearest_airport(req.origin.lat, req.origin.lng)
    dest_ap = airport_by_iata(dest.airport)
    est = estimate_flight(origin_ap, dest_ap) if dest_ap else {"flight_hours": 0.0, "flight_time": ""}

    scored = ScoredDestination(
        destination=dest,  # type: ignore[arg-type]  # duck-typed: same shape as Destination
        distance_miles=est.get("distance_miles", 0),
        drive_hours=est["flight_hours"],
        drive_time=est["flight_time"],
        score=0.0,
    )

    plan_req = PlanRequest(
        origin=req.origin,
        trip_type=req.trip_type,
        start_date=req.start_date,
        end_date=req.end_date,
        max_drive_hours=8.0,
        max_flight_hours=8.0,
        preferences=req.preferences,
        allow_flight=True,
        language=req.language,
    )
    weather, (food, fun, events) = await asyncio.gather(
        fetch_weather_note(dest.lat, dest.lng, req.language),
        _local_highlights(dest.lat, dest.lng, req.start_date),
    )

    summary_prompt = (
        f"Write 2-3 sentences for a spontaneous fly-away trip plan.\n"
        f"Fly from {origin_ap.iata} to {dest.name} ({dest.highlight})\n"
        f"Flight: about {est['flight_time']}\n"
        f"Trip type: {req.trip_type}\n"
        f"Weather: {weather}\n"
        f"Tone: enthusiastic but practical.\n"
        f"Respond in {lang_name(req.language)}. Keep place names in English."
    )
    summary = await generate_summary(summary_prompt)
    if not summary:
        summary = tr(
            "fly_summary_fallback",
            req.language,
            name=dest.name,
            highlight=dest.highlight,
            time=est["flight_time"],
            airport=origin_ap.iata,
        )

    itinerary = _build_itinerary(plan_req, scored, [], weather, summary, food, fun, events)
    return itinerary.model_copy(
        update={
            "travel_mode": "fly",
            "origin_airport": origin_ap.iata,
            "destination_airport": dest.airport,
        }
    )
