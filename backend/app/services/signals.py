"""Ranking signal providers (pluggable).

The design doc's ranking formula (§10) needs three signals the base hybrid
retriever didn't have: **weather compatibility**, **popularity**, **freshness**.

These are exposed behind a small `SignalProvider` protocol so the *source* can
be swapped later without touching the ranker:

  - now (zero-key):  `HeuristicSignalProvider` derives signals from the curated
    corpus text/tags + season, and weather from the one weather note we already
    fetch.
  - later (scale):   a `GooglePlacesSignalProvider` / DB-backed provider could
    return real ratings (popularity), opening-hours/seasonality (freshness),
    etc. Implement the same protocol and swap `signal_provider`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class WeatherCondition:
    """Coarse, source-agnostic weather state parsed from a weather note."""

    rainy: bool = False
    cold: bool = False
    hot: bool = False
    unknown: bool = True


_RAIN_WORDS = ("rain", "shower", "storm", "drizzle", "snow", "雨", "雪", "暴")
_COLD_WORDS = ("cold", "freez", "chilly", "snow", "冷", "寒")
_HOT_WORDS = ("hot", "heat", "scorch", "热", "炎")
_TEMP_RE = re.compile(r"(-?\d{1,3})\s*°?\s*(f|c|℉|℃|度)?", re.I)


def parse_weather_note(note: str) -> WeatherCondition:
    """Best-effort parse of a free-text weather note (EN/ZH) into flags."""
    if not note:
        return WeatherCondition()
    low = note.lower()
    rainy = any(w in low for w in _RAIN_WORDS)
    cold = any(w in low for w in _COLD_WORDS)
    hot = any(w in low for w in _HOT_WORDS)
    # Temperature hint (assume Fahrenheit if unit missing — backend uses imperial).
    m = _TEMP_RE.search(low)
    if m:
        try:
            temp = int(m.group(1))
            unit = (m.group(2) or "f").lower()
            f = temp if unit.startswith("f") or unit in ("℉",) else temp * 9 / 5 + 32
            if f <= 40:
                cold = True
            elif f >= 88:
                hot = True
        except ValueError:
            pass
    known = rainy or cold or hot or bool(m)
    return WeatherCondition(rainy=rainy, cold=cold, hot=hot, unknown=not known)


# Tags / words that read as "indoor-friendly" vs "outdoor-exposed".
_INDOOR_HINTS = (
    "city-walk", "city walk", "museum", "gallery", "indoor", "market",
    "escape room", "aquarium", "cafe", "shopping", "室内",
)
_OUTDOOR_HINTS = (
    "national-park", "hiking", "forest", "beach", "trail", "summit",
    "canyon", "coast", "surf", "kayak", "camp", "户外", "徒步",
)

_POPULAR_HINTS = (
    "national park", "iconic", "famous", "popular", "world-famous",
    "must-see", "landmark", "classic", "renowned", "unesco",
)
_FRESH_HINTS = (
    "seasonal", "festival", "new", "pop-up", "limited", "trending",
    "just opened", "this season", "aurora", "whale", "wildflower",
)


@runtime_checkable
class SignalProvider(Protocol):
    """Source of popularity / freshness / weather signals for ranking."""

    def popularity(self, *, text: str, tags: tuple[str, ...]) -> float: ...

    def freshness(self, *, text: str, tags: tuple[str, ...], start_date: str = "") -> float: ...

    def weather_compat(
        self, *, text: str, tags: tuple[str, ...], weather: WeatherCondition | None
    ) -> float: ...


class HeuristicSignalProvider:
    """Zero-key implementation derived from curated corpus text + season.

    All scores are normalized to [0, 1]; 0.5 is neutral so a missing signal
    never dominates the weighted sum.
    """

    def _is_indoor(self, blob: str) -> bool:
        return any(h in blob for h in _INDOOR_HINTS)

    def _is_outdoor(self, blob: str) -> bool:
        return any(h in blob for h in _OUTDOOR_HINTS)

    def popularity(self, *, text: str, tags: tuple[str, ...]) -> float:
        blob = text.lower()
        score = 0.45
        score += 0.12 * sum(1 for h in _POPULAR_HINTS if h in blob)
        # Richer catalog entries (more listed highlights) skew slightly popular.
        score += min(0.15, 0.03 * blob.count(";"))
        score += min(0.1, 0.02 * len(tags))
        return max(0.0, min(1.0, score))

    def freshness(self, *, text: str, tags: tuple[str, ...], start_date: str = "") -> float:
        blob = text.lower()
        score = 0.5
        score += 0.12 * sum(1 for h in _FRESH_HINTS if h in blob)
        # Seasonal nudge: summer→beach/surf, winter→aurora/snow.
        month = _month_of(start_date)
        if month is not None:
            summer = month in (6, 7, 8)
            winter = month in (12, 1, 2)
            if summer and any(w in blob for w in ("beach", "surf", "swim", "kayak")):
                score += 0.15
            if winter and any(w in blob for w in ("aurora", "snow", "ski", "northern light")):
                score += 0.15
        return max(0.0, min(1.0, score))

    def weather_compat(
        self, *, text: str, tags: tuple[str, ...], weather: WeatherCondition | None
    ) -> float:
        if weather is None or weather.unknown:
            return 0.6  # neutral-positive when we don't know
        blob = (text + " " + " ".join(tags)).lower()
        indoor = self._is_indoor(blob)
        outdoor = self._is_outdoor(blob) and not indoor
        if weather.rainy:
            return 0.85 if indoor else (0.3 if outdoor else 0.55)
        if weather.cold:
            return 0.8 if indoor else (0.45 if outdoor else 0.6)
        if weather.hot:
            # Hot favors water/shade-ish outdoor; penalize strenuous exposure a bit.
            if any(w in blob for w in ("beach", "surf", "lake", "swim", "kayak")):
                return 0.9
            return 0.7 if indoor else 0.55
        # Clear / mild → outdoor shines.
        return 0.9 if outdoor else 0.7


def _month_of(start_date: str) -> int | None:
    try:
        return date.fromisoformat(start_date).month
    except (ValueError, TypeError):
        return None


# Module singleton — swap this to change signal source app-wide.
signal_provider: SignalProvider = HeuristicSignalProvider()
