from __future__ import annotations

import asyncio

import httpx

from app.models.schemas import Preference
from app.services import flights_api
from app.services.airports import Airport, airport_by_iata, nearest_airport
from app.services.fly_destinations import FLY_DESTINATIONS, FlyDestination
from app.services.geo import format_duration, haversine_miles

_AVG_CRUISE_MPH = 500.0
_FLIGHT_OVERHEAD_H = 0.5  # taxi, climb, descent


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


def _parse_offer(itinerary: dict) -> dict | None:
    try:
        legs = itinerary["legs"]
        first, last = legs[0], legs[-1]
        total_minutes = sum(leg.get("durationInMinutes", 0) for leg in legs)
        carriers = first.get("carriers", {}).get("marketing", [])
        carrier = carriers[0].get("name", "") if carriers else ""
        price = itinerary.get("price", {})
        return {
            "price": price.get("formatted", str(price.get("raw", ""))).lstrip("$"),
            "currency": "USD",
            "duration": format_duration(total_minutes / 60),
            "stops": max((leg.get("stopCount", 0) for leg in legs), default=0),
            "carrier": carrier,
            "depart_airport": first.get("origin", {}).get("id", ""),
            "depart_at": first.get("departure", ""),
            "arrive_airport": last.get("destination", {}).get("id", ""),
            "arrive_at": last.get("arrival", ""),
        }
    except (KeyError, IndexError):
        return None


async def search_offers(
    origin_iata: str, dest_iata: str, departure_date: str, adults: int = 1, max_results: int = 5
) -> list[dict]:
    """Return real flight offers from the flights provider, or [] if unavailable."""
    if not flights_api.is_configured():
        return []

    params = flights_api.query(
        fromEntityId=origin_iata,
        toEntityId=dest_iata,
        departDate=departure_date,
        adults=adults,
    )
    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            resp = await client.get(
                flights_api.url(flights_api.SEARCH_ONE_WAY),
                params=params,
                headers=flights_api.headers(),
            )
            resp.raise_for_status()
            itineraries = resp.json().get("data", {}).get("itineraries", [])
    except Exception:
        return []

    offers: list[dict] = []
    for itinerary in sorted(itineraries, key=lambda it: it.get("price", {}).get("raw", 1e9)):
        parsed = _parse_offer(itinerary)
        if parsed:
            offers.append(parsed)
        if len(offers) >= max_results:
            break
    return offers


async def _fetch_calendar(
    client: httpx.AsyncClient, origin_iata: str, dest_iata: str, depart_date: str
) -> list[dict]:
    """Raw daily-price list [{day, group, price}, ...] from cheapest-one-way, or []."""
    params = flights_api.query(
        fromEntityId=origin_iata,
        toEntityId=dest_iata,
        departDate=depart_date,
    )
    try:
        resp = await client.get(
            flights_api.url(flights_api.CHEAPEST_ONE_WAY),
            params=params,
            headers=flights_api.headers(),
        )
        resp.raise_for_status()
        data = resp.json().get("data") or []
    except Exception:
        return []
    return [d for d in data if isinstance(d, dict) and d.get("price") is not None]


def _summarize_calendar(days: list[dict]) -> dict:
    if not days:
        return {}
    cheapest = min(days, key=lambda d: d["price"])
    by_day = sorted(days, key=lambda d: d.get("day", ""))
    return {
        "starting_price": round(cheapest["price"]),
        "cheapest_day": cheapest.get("day", ""),
        "currency": "USD",
        "days": [
            {"day": d.get("day", ""), "price": round(d["price"]), "group": d.get("group", "")}
            for d in by_day
        ],
    }


async def price_calendar(origin_iata: str, dest_iata: str, depart_date: str) -> dict:
    """Cheapest price + per-day calendar for a route, or {} if unavailable."""
    if not flights_api.is_configured():
        return {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        days = await _fetch_calendar(client, origin_iata, dest_iata, depart_date)
    return _summarize_calendar(days)


async def cheapest_prices(
    origin_iata: str, routes: list[tuple[str, str]], depart_date: str, max_concurrency: int = 4
) -> dict[str, dict]:
    """Best-effort starting price + cheapest day per route.

    routes: list of (destination_name, destination_iata).
    Returns {destination_name: {starting_price, cheapest_day, currency}}.
    """
    if not flights_api.is_configured() or not routes:
        return {}

    sem = asyncio.Semaphore(max_concurrency)
    result: dict[str, dict] = {}

    async with httpx.AsyncClient(timeout=30.0) as client:

        async def one(name: str, dest_iata: str) -> None:
            async with sem:
                days = await _fetch_calendar(client, origin_iata, dest_iata, depart_date)
            summary = _summarize_calendar(days)
            if summary:
                result[name] = {
                    "starting_price": summary["starting_price"],
                    "cheapest_day": summary["cheapest_day"],
                    "currency": summary["currency"],
                }

        await asyncio.gather(*(one(n, i) for n, i in routes), return_exceptions=True)

    return result
