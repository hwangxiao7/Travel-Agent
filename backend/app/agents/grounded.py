from __future__ import annotations

from app.models.schemas import Activity, DayPlan, Event, Place
from app.services.i18n import lang_name
from app.services.llm import generate_summary, parse_itinerary_json


def _places_line(places: list[Place]) -> str:
    if not places:
        return "none found"
    return ", ".join(f"{p.name}{f' ({p.note})' if p.note else ''}" for p in places[:8])


def _events_line(events: list[Event]) -> str:
    if not events:
        return "none found"
    return ", ".join(f"{e.name} ({e.date})" if e.date else e.name for e in events[:5])


def _valid_activity(a: dict) -> bool:
    return isinstance(a, dict) and bool(a.get("place"))


def _flat_activities(parsed: dict | None) -> list[dict] | None:
    """Pull a flat activity list out of whatever shape the model returned.

    Primary schema is {"activities":[{"day":1,...}]}, but we also tolerate a
    nested {"days":[{"activities":[...]}]} form by flattening with day indices."""
    if not isinstance(parsed, dict):
        return None
    acts = parsed.get("activities")
    if isinstance(acts, list):
        return acts

    days = parsed.get("days")
    if isinstance(days, dict):
        days = [days]
    if isinstance(days, list):
        flat: list[dict] = []
        for i, day in enumerate(days, start=1):
            day_acts = day.get("activities", []) if isinstance(day, dict) else []
            if isinstance(day_acts, list):
                for a in day_acts:
                    if isinstance(a, dict):
                        a.setdefault("day", i)
                        flat.append(a)
        return flat or None
    return None


async def generate_grounded_days(
    *,
    destination: str,
    region: str,
    highlight: str,
    context: str,
    base_days: list[DayPlan],
    nearby_food: list[Place],
    nearby_fun: list[Place],
    events: list[Event],
    weather_note: str,
    preferences: list[str],
    language: str,
) -> list[DayPlan] | None:
    """Ask the LLM to write day-by-day activities grounded in retrieved facts.

    Returns None (so the caller keeps the curated catalog itinerary) when no LLM
    is configured or the response can't be parsed into the expected shape."""
    day_count = len(base_days)
    if day_count == 0:
        return None

    prompt = (
        "You are a meticulous travel planner. Using ONLY the grounded facts below, "
        f"write a {day_count}-day itinerary (days numbered 1..{day_count}) for "
        f"{destination} ({region}).\n\n"
        f"Overview: {highlight}\n"
        f"Reference context: {context}\n"
        f"Nearby places to eat: {_places_line(nearby_food)}\n"
        f"Nearby things to do: {_places_line(nearby_fun)}\n"
        f"Local events: {_events_line(events)}\n"
        f"Weather: {weather_note}\n"
        f"Traveler preferences: {', '.join(preferences) or 'general outdoor'}\n\n"
        "Rules:\n"
        "- Prefer real place names from the facts above; do not invent landmarks.\n"
        "- Include at least one nearby food stop per day when available.\n"
        "- 3 to 5 timed activities per day, realistic ordering and durations.\n"
        "- Adapt to the weather note when relevant.\n"
        f"- Keep place names in English; write the 'note' field in {lang_name(language)}.\n\n"
        "Respond with ONLY a JSON object using this flat schema (one array; use the "
        "1-based 'day' field to say which day each activity belongs to):\n"
        '{"activities":[{"day":1,"time":"09:00","place":"Tunnel View",'
        '"duration":"1h","note":"..."}]}'
    )

    raw = await generate_summary(prompt, json_mode=True)
    if not raw:
        return None

    activities = _flat_activities(parse_itinerary_json(raw))
    if not activities:
        return None

    # Group flat activities by their 1-based day index onto the dated base days.
    by_day: dict[int, list[Activity]] = {}
    for a in activities:
        if not _valid_activity(a):
            continue
        try:
            day_idx = int(a.get("day", 1))
        except (TypeError, ValueError):
            day_idx = 1
        day_idx = min(max(day_idx, 1), day_count)
        by_day.setdefault(day_idx, []).append(
            Activity(
                time=str(a.get("time", "")),
                place=str(a["place"]),
                duration=str(a.get("duration", "")),
                note=str(a.get("note", "")),
            )
        )

    out: list[DayPlan] = []
    for i, base in enumerate(base_days, start=1):
        acts = by_day.get(i, [])
        out.append(DayPlan(date=base.date, activities=acts) if acts else base)

    if all(not d.activities for d in out):
        return None
    return out
