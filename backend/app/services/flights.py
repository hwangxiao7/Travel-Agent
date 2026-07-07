from __future__ import annotations

import re
import time

import httpx

from app.config import settings
from app.models.schemas import Preference
from app.services.airports import Airport, airport_by_iata, nearest_airport
from app.services.fly_destinations import FLY_DESTINATIONS, FlyDestination
from app.services.geo import format_duration, haversine_miles

_AVG_CRUISE_MPH = 500.0
_FLIGHT_OVERHEAD_H = 0.5  # taxi, climb, descent

_token_cache: dict[str, float | str] = {"value": "", "expires_at": 0.0}


def estimate_flight(origin: Airport, dest: Airport) -> dict:
    miles = haversine_miles(origin.lat, origin.lng, dest.lat, dest.lng)
    hours = miles / _AVG_CRUISE_MPH + _FLIGHT_OVERHEAD_H
    return {
        "distance_miles": round(miles),
        "flight_hours": round(hours, 2),
        "flight_time": format_duration(hours),
        "origin_airport": origin.iata,
        "destination_airport": dest.iata,
    }


def _pref_score(dest: FlyDestination, prefs: list[Preference]) -> float:
    if not prefs:
        return 1.0
    overlap = len(set(dest.tags) & set(prefs))
    return overlap / len(set(prefs))


def fly_candidates(
    origin_lat: float, origin_lng: float, max_flight_hours: float, preferences: list[Preference]
) -> tuple[Airport, list[dict]]:
    origin_ap = nearest_airport(origin_lat, origin_lng)
    scored: list[tuple[float, float, dict]] = []
    for d in FLY_DESTINATIONS:
        dest_ap = airport_by_iata(d.airport)
        if dest_ap is None:
            continue
        est = estimate_flight(origin_ap, dest_ap)
        if est["flight_hours"] > max_flight_hours:
            continue
        pref = _pref_score(d, preferences)
        scored.append(
            (
                pref,
                est["flight_hours"],
                {
                    "name": d.name,
                    "lat": d.lat,
                    "lng": d.lng,
                    "region": d.region,
                    "airport": d.airport,
                    "highlight": d.highlight,
                    "flight_time": est["flight_time"],
                    "flight_hours": est["flight_hours"],
                    "distance_miles": est["distance_miles"],
                },
            )
        )
    scored.sort(key=lambda x: (-x[0], x[1]))
    return origin_ap, [item for _, _, item in scored]


def _parse_iso_duration(value: str) -> str:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", value or "")
    if not m:
        return value
    h = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    return format_duration(h + mins / 60)


async def _get_token() -> str:
    if not (settings.amadeus_api_key and settings.amadeus_api_secret):
        return ""
    now = time.time()
    if _token_cache["value"] and float(_token_cache["expires_at"]) > now + 30:
        return str(_token_cache["value"])

    url = f"{settings.amadeus_base_url}/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": settings.amadeus_api_key,
        "client_secret": settings.amadeus_api_secret,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            payload = resp.json()
        _token_cache["value"] = payload["access_token"]
        _token_cache["expires_at"] = now + payload.get("expires_in", 1800)
        return str(_token_cache["value"])
    except Exception:
        return ""


async def search_offers(
    origin_iata: str, dest_iata: str, departure_date: str, adults: int = 1, max_results: int = 5
) -> list[dict]:
    """Return real flight offers from Amadeus, or [] if unavailable."""
    token = await _get_token()
    if not token:
        return []

    url = f"{settings.amadeus_base_url}/v2/shopping/flight-offers"
    params = {
        "originLocationCode": origin_iata,
        "destinationLocationCode": dest_iata,
        "departureDate": departure_date,
        "adults": adults,
        "currencyCode": "USD",
        "max": max_results,
    }
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json().get("data", [])
    except Exception:
        return []

    offers: list[dict] = []
    for offer in data:
        try:
            itinerary = offer["itineraries"][0]
            segments = itinerary["segments"]
            first, last = segments[0], segments[-1]
            offers.append(
                {
                    "price": offer["price"]["total"],
                    "currency": offer["price"].get("currency", "USD"),
                    "duration": _parse_iso_duration(itinerary.get("duration", "")),
                    "stops": len(segments) - 1,
                    "carrier": first.get("carrierCode", ""),
                    "depart_airport": first["departure"]["iataCode"],
                    "depart_at": first["departure"]["at"],
                    "arrive_airport": last["arrival"]["iataCode"],
                    "arrive_at": last["arrival"]["at"],
                }
            )
        except (KeyError, IndexError):
            continue
    return offers
