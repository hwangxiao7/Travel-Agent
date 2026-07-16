from __future__ import annotations

from app.models.schemas import Activity, DayPlan, Event, Place
from app.services.i18n import lang_name
from app.services.llm import generate_summary, parse_itinerary_json

# Fixed instructions live in the system message so the per-request user prompt
# stays lean (just the facts) and the shared prefix can be cached across calls.
_GROUNDED_SYSTEM = (
    "You are a meticulous travel planner. Build day-by-day itineraries grounded "
    "ONLY in the facts the user gives.\n"
    "Rules:\n"
    "- Use real place names from those facts; never invent landmarks.\n"
    "- With traveler history, favor liked themes and avoid past dislikes.\n"
    "- Match the trip vibe: low energy -> fewer relaxed stops; romantic -> cozy "
    "scenic pairs; friends -> lively shared activities.\n"
    "- At least one food stop per day when available.\n"
    "- 3-5 timed activities per day, realistic order and durations.\n"
    "- Adapt to the weather. Keep place names in English.\n"
    'Output ONLY a JSON object (1-based "day" field per activity):\n'
    '{"activities":[{"day":1,"time":"09:00","place":"Tunnel View",'
    '"duration":"1h","note":"..."}]}'
)


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


def validate_grounded_output(
    days: list[DayPlan],
    *,
    known_places: set[str],
    context: str,
) -> dict:
    """Post-generation checks: place coverage vs known POIs / context (step 8)."""
    places = [a.place for d in days for a in d.activities if a.place]
    if not places:
        return {"ok": False, "groundedness": 0.0, "hallucination_rate": 1.0, "n_places": 0}
    ctx = context.lower()
    known_l = {p.lower() for p in known_places}
    grounded = 0
    halluc = 0
    for p in places:
        pl = p.lower()
        in_known = any(pl in k or k in pl for k in known_l) if known_l else False
        in_ctx = pl in ctx or any(tok in ctx for tok in pl.split() if len(tok) > 3)
        if in_known or in_ctx:
            grounded += 1
        else:
            halluc += 1
    n = len(places)
    return {
        "ok": halluc / n <= 0.4,
        "groundedness": round(grounded / n, 3),
        "hallucination_rate": round(halluc / n, 3),
        "n_places": n,
    }


def _merge_grounding_context(base: str, rag_context: str = "") -> str:
    """Combine destination blurb with retrieved RAG blocks (docs + memory)."""
    parts = [p.strip() for p in (base, rag_context) if p and p.strip()]
    if not parts:
        return ""
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        key = p.lower()[:160]
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return "\n\n".join(out)


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
    profile_note: str = "",
    rag_context: str = "",
    framing_note: str = "",
) -> list[DayPlan] | None:
    """Ask the LLM to write day-by-day activities grounded in retrieved facts.

    `context` is the destination catalog blurb; `rag_context` is optional
    multi-doc retrieval (top destinations + user memory) from the RAG pipeline.
    Returns None when no LLM is configured or parsing fails."""
    day_count = len(base_days)
    if day_count == 0:
        return None

    full_context = _merge_grounding_context(context, rag_context)

    prompt = (
        f"Write a {day_count}-day itinerary (days 1..{day_count}) for "
        f'{destination} ({region}). Write each "note" in {lang_name(language)}.\n\n'
        f"Overview: {highlight}\n"
        f"Facts (prefer these; do not invent):\n{full_context or '(none)'}\n"
        f"Eat nearby: {_places_line(nearby_food)}\n"
        f"Do nearby: {_places_line(nearby_fun)}\n"
        f"Events: {_events_line(events)}\n"
        f"Weather: {weather_note}\n"
        f"Preferences: {', '.join(preferences) or 'general outdoor'}\n"
        f"{('Vibe: ' + framing_note + chr(10)) if framing_note else ''}"
        f"{('History: ' + profile_note + chr(10)) if profile_note else ''}"
    )

    raw = await generate_summary(prompt, json_mode=True, system=_GROUNDED_SYSTEM)
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


def grounding_context_used(base: str, rag_context: str = "") -> str:
    """Public helper so planners validate against the same merged context."""
    return _merge_grounding_context(base, rag_context)
