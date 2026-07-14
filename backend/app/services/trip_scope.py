"""Trip range: local short-play vs away trips.

Two independent *user choices* (not coupled filters):
  - how far you'll drive (max_drive_hours)
  - whether you'll fly (allow_flight)

Shared *product intent*:
  - local_play: drive ≤5h (≤3h local fun; 3–5h gray, still short-trip)
  - away: drive ≥5h OR fly — leave local short tourism; destination trips,
    not “find something fun nearby”
"""

from __future__ import annotations

from typing import Literal

TripScope = Literal["local", "regional", "distant"]
TripKind = Literal["local_play", "away"]
# UI group: drive bands + fly (fly is not a drive band; both away kinds stay separate).
DisplayGroup = Literal["local", "regional", "distant", "fly"]

LOCAL_MAX_HOURS = 3.0
REGIONAL_MAX_HOURS = 5.0

_SCOPE_ORDER = {"local": 0, "regional": 1, "distant": 2, "fly": 3}

_LABELS = {
    "en": {
        "local": "Local fun (≤3h drive)",
        "regional": "Short getaway (3–5h drive)",
        "distant": "Away · long drive (5h+)",
        "fly": "Away · fly",
        "local_play": "Local short trips",
        "away": "Away from home (not local play)",
    },
    "zh": {
        "local": "本地找好玩（开车 ≤3 小时）",
        "regional": "短途灰度（开车 3–5 小时）",
        "distant": "出本地 · 长途开车（5 小时+）",
        "fly": "出本地 · 坐飞机",
        "local_play": "本地短途",
        "away": "出本地（不是本地找好玩）",
    },
}


def classify_trip_scope(*, hours: float) -> TripScope:
    """Drive-time band only. Do not pass flight hours here."""
    h = max(0.0, float(hours or 0.0))
    if h <= LOCAL_MAX_HOURS:
        return "local"
    if h < REGIONAL_MAX_HOURS:
        return "regional"
    return "distant"


def classify_trip_kind(*, travel_mode: str = "drive", hours: float = 0.0) -> TripKind:
    """local_play vs away. Fly and long drive are both away; still independent choices."""
    if (travel_mode or "drive") == "fly":
        return "away"
    if classify_trip_scope(hours=hours) == "distant":
        return "away"
    return "local_play"


def display_group(*, travel_mode: str = "drive", hours: float) -> DisplayGroup:
    if (travel_mode or "drive") == "fly":
        return "fly"
    return classify_trip_scope(hours=hours)


def trip_scope_label(scope: str, language: str = "en") -> str:
    lang = "zh" if (language or "").lower().startswith("zh") else "en"
    return _LABELS[lang].get(scope, scope)


def trip_scope_order(scope: str) -> int:
    return _SCOPE_ORDER.get(scope, 9)


def distance_preference(*, travel_mode: str = "drive", hours: float) -> float:
    """Soft 0–1: prefer local_play; within away, mild shorter-is-better."""
    h = max(0.0, float(hours or 0.0))
    if (travel_mode or "drive") == "fly":
        return max(0.20, 0.55 - min(h, 6.0) * 0.05)

    scope = classify_trip_scope(hours=h)
    if scope == "local":
        return max(0.65, 1.0 - h / LOCAL_MAX_HOURS * 0.30)
    if scope == "regional":
        return max(0.40, 0.72 - (h - LOCAL_MAX_HOURS) / 2.0 * 0.28)
    return max(0.12, 0.38 - min(h, 8.0) * 0.03)


def annotate_candidate(payload: dict, *, travel_mode: str | None = None) -> dict:
    """Attach travel_mode, drive trip_scope, and trip_kind (local_play | away)."""
    mode = travel_mode or payload.get("travel_mode") or (
        "fly" if payload.get("source") == "fly" else "drive"
    )
    hours = float(payload.get("drive_hours") or 0.0)
    payload["travel_mode"] = mode
    kind = classify_trip_kind(travel_mode=mode, hours=hours)
    payload["trip_kind"] = kind
    payload["trip_kind_label"] = trip_scope_label(kind)

    group = display_group(travel_mode=mode, hours=hours)
    payload["display_group"] = group
    if mode == "fly":
        payload["trip_scope"] = None
        payload["trip_scope_label"] = trip_scope_label("fly")
    else:
        scope = classify_trip_scope(hours=hours)
        payload["trip_scope"] = scope
        payload["trip_scope_label"] = trip_scope_label(scope)
    return payload
