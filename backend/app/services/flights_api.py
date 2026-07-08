"""Central configuration for the external flights provider.

Everything provider-specific lives here: host, endpoint paths, shared query
defaults, and auth headers. To swap providers or change an endpoint later,
edit this file (and `rapidapi_flights_host` / `rapidapi_key` in `.env`) —
`flights.py` reads all external-API details from here.

Current provider: Flights Scraper Sky (RapidAPI) — https://rapidapi.com/ntd119/api/flights-sky
"""

from __future__ import annotations

from app.config import settings

# --- Endpoint paths on the current provider ---
SEARCH_ONE_WAY = "/flights/search-one-way"
CHEAPEST_ONE_WAY = "/flights/cheapest-one-way"

# --- Shared query defaults sent with every request ---
DEFAULT_QUERY: dict[str, str] = {
    "currency": "USD",
    "market": "US",
    "locale": "en-US",
}


def is_configured() -> bool:
    return bool(settings.rapidapi_key)


def url(path: str) -> str:
    return f"https://{settings.rapidapi_flights_host}{path}"


def headers() -> dict[str, str]:
    return {
        "x-rapidapi-key": settings.rapidapi_key,
        "x-rapidapi-host": settings.rapidapi_flights_host,
    }


def query(**overrides: object) -> dict[str, object]:
    """Merge caller params on top of the shared defaults."""
    return {**DEFAULT_QUERY, **overrides}
