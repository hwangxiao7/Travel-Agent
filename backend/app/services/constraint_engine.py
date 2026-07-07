from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import PlanRequest, Preference
from app.services.destinations import DESTINATIONS, Destination
from app.services.geo import estimate_drive_hours, format_duration, haversine_miles


@dataclass
class ScoredDestination:
    destination: Destination
    distance_miles: float
    drive_hours: float
    drive_time: str
    score: float


def _preference_score(dest: Destination, prefs: list[Preference]) -> float:
    if not prefs:
        return 1.0
    dest_tags = set(dest.tags)
    wanted = set(prefs)
    overlap = len(dest_tags & wanted)
    return overlap / len(wanted)


def find_candidates(request: PlanRequest, limit: int = 5) -> list[ScoredDestination]:
    max_hours = request.max_drive_hours
    if request.trip_type == "weekend" and request.allow_flight:
        max_hours = max(max_hours, request.max_flight_hours + 1.5)

    scored: list[ScoredDestination] = []
    for dest in DESTINATIONS:
        miles = haversine_miles(request.origin.lat, request.origin.lng, dest.lat, dest.lng)
        hours = estimate_drive_hours(miles)
        if hours > max_hours:
            continue
        pref = _preference_score(dest, request.preferences)
        # Prefer closer + better preference match
        score = pref * 10 - hours * 0.5
        scored.append(
            ScoredDestination(
                destination=dest,
                distance_miles=round(miles, 1),
                drive_hours=round(hours, 2),
                drive_time=format_duration(hours),
                score=score,
            )
        )

    scored.sort(key=lambda x: x.score, reverse=True)
    return scored[:limit]
