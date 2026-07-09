from __future__ import annotations

import httpx

# Free public OSRM demo server — real road routing, no key required.
# Used to replace the straight-line drive-time estimate with actual durations.
OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving/"


async def drive_durations_hours(
    origin_lat: float,
    origin_lng: float,
    coords: list[tuple[float, float]],
) -> list[float | None] | None:
    """Real driving time (hours) from one origin to many destinations.

    Uses the OSRM `table` service so all destinations resolve in a single
    request. Returns a list aligned with `coords` (None for any unroutable
    point), or None if the whole lookup fails so callers fall back to the
    haversine estimate."""
    from app.observability import atraced, external_api_latency_ms, record_external_failure

    if not coords:
        return []

    # OSRM expects "lng,lat" pairs; origin is index 0 (the only source).
    points = [f"{origin_lng},{origin_lat}"] + [f"{lng},{lat}" for lat, lng in coords]
    path = ";".join(points)
    params = {"sources": "0", "annotations": "duration"}

    async with atraced(
        "routing.OSRM call",
        attributes={"osrm.destinations": len(coords)},
        latency_metric=external_api_latency_ms,
        latency_labels={"api": "osrm"},
    ):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(OSRM_TABLE_URL + path, params=params)
                resp.raise_for_status()
                data = resp.json()
            if data.get("code") != "Ok":
                record_external_failure("osrm")
                return None
            row = data["durations"][0]  # origin -> each point (seconds), incl. self at [0]
        except Exception:
            record_external_failure("osrm")
            return None

        out: list[float | None] = []
        for secs in row[1:]:  # skip origin->origin
            out.append(round(secs / 3600.0, 2) if isinstance(secs, (int, float)) else None)
        return out


async def drive_duration_hours(
    origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float
) -> float | None:
    """Real driving time (hours) for a single destination."""
    result = await drive_durations_hours(origin_lat, origin_lng, [(dest_lat, dest_lng)])
    if not result:
        return None
    return result[0]
