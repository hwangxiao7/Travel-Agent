from __future__ import annotations

import httpx

from app.config import settings
from app.models.schemas import Event

# Ticketmaster Discovery API — free tier, key-gated.
# Without a key we return [] so the rest of the plan still works.
DISCOVERY_URL = "https://app.ticketmaster.com/discovery/v2/events.json"


def _parse_event(raw: dict) -> Event | None:
    name = raw.get("name")
    if not name:
        return None

    dates = raw.get("dates", {}).get("start", {})
    date = dates.get("localDate", "")
    time = dates.get("localTime", "")
    if date and time:
        date = f"{date} {time[:5]}"

    venue = ""
    venues = raw.get("_embedded", {}).get("venues", [])
    if venues:
        venue = venues[0].get("name", "")

    category = ""
    classifications = raw.get("classifications", [])
    if classifications:
        seg = classifications[0].get("segment", {})
        genre = classifications[0].get("genre", {})
        category = genre.get("name") or seg.get("name") or ""
        if category in ("Undefined", "Other"):
            category = seg.get("name", "")

    return Event(
        name=name,
        date=date,
        venue=venue,
        category=category,
        url=raw.get("url", ""),
    )


async def fetch_events(
    lat: float,
    lng: float,
    start_date: str = "",
    radius_miles: int = 50,
    limit: int = 6,
) -> list[Event]:
    """Return upcoming ticketed events near a destination (Ticketmaster).

    Best-effort: no key or any failure returns []."""
    if not settings.ticketmaster_api_key:
        return []

    params = {
        "apikey": settings.ticketmaster_api_key,
        "latlong": f"{lat},{lng}",
        "radius": str(radius_miles),
        "unit": "miles",
        "size": str(limit),
        "sort": "date,asc",
    }
    if start_date:
        params["startDateTime"] = f"{start_date}T00:00:00Z"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(DISCOVERY_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        from app.observability import record_external_failure

        record_external_failure("ticketmaster", str(exc))
        return []

    raw_events = data.get("_embedded", {}).get("events", [])
    events: list[Event] = []
    seen: set[str] = set()
    for raw in raw_events:
        event = _parse_event(raw)
        if event is None or event.name.lower() in seen:
            continue
        seen.add(event.name.lower())
        events.append(event)
    return events[:limit]
