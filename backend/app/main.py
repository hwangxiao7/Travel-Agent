from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.agents.planner import (
    create_plan,
    plan_for_destination,
    plan_for_fly_destination,
    search_destinations,
)
from app.agents.refiner import refine
from app.config import settings
from app.models.schemas import (
    CalendarRequest,
    CalendarResponse,
    ChatRequest,
    ChatResponse,
    FlightsRequest,
    FlightsResponse,
    FlyDestinationItem,
    FlyDestinationsRequest,
    FlyDestinationsResponse,
    FlyPlanRequest,
    FlyPricesRequest,
    FlyPricesResponse,
    PlanRequest,
    PlanResponse,
    PriceSummary,
    SearchRequest,
    SearchResponse,
    SelectRequest,
    SelectResponse,
)
from app.services.airports import airport_by_iata, nearest_airport
from app.services.destinations import DESTINATIONS
from app.services.flights import (
    cheapest_prices,
    estimate_flight,
    fly_candidates,
    price_calendar,
    search_offers,
)
from app.services.fly_destinations import FLY_DESTINATIONS
from app.services.geocode import geocode

app = FastAPI(title="Spontaneous Travel Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok", "destinations": len(DESTINATIONS)}


@app.get("/api/geocode")
async def geocode_address(q: str):
    return {"results": await geocode(q)}


@app.post("/api/plan", response_model=PlanResponse)
async def plan_trip(request: PlanRequest):
    try:
        itinerary, candidates = await create_plan(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PlanResponse(itinerary=itinerary, candidates=candidates)


@app.post("/api/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    try:
        itinerary, candidates, semantic = await search_destinations(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SearchResponse(itinerary=itinerary, candidates=candidates, semantic=semantic)


@app.post("/api/select", response_model=SelectResponse)
async def select_destination(request: SelectRequest):
    try:
        itinerary = await plan_for_destination(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SelectResponse(itinerary=itinerary)


@app.post("/api/fly-destinations", response_model=FlyDestinationsResponse)
async def list_fly_destinations(request: FlyDestinationsRequest):
    origin_ap, items = fly_candidates(
        request.origin.lat, request.origin.lng, request.max_flight_hours, request.preferences
    )
    return FlyDestinationsResponse(
        origin_airport=origin_ap.iata,
        destinations=[FlyDestinationItem(**item) for item in items],
    )


@app.post("/api/fly-plan", response_model=SelectResponse)
async def fly_plan(request: FlyPlanRequest):
    try:
        itinerary = await plan_for_fly_destination(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return SelectResponse(itinerary=itinerary)


@app.post("/api/flights", response_model=FlightsResponse)
async def flights(request: FlightsRequest):
    dest = next((d for d in FLY_DESTINATIONS if d.name == request.destination_name), None)
    if dest is None:
        raise HTTPException(status_code=422, detail=f"Unknown fly destination: {request.destination_name}")

    origin_ap = nearest_airport(request.origin.lat, request.origin.lng)
    dest_ap = airport_by_iata(dest.airport)
    estimate = estimate_flight(origin_ap, dest_ap) if dest_ap else {}
    offers = await search_offers(origin_ap.iata, dest.airport, request.departure_date, request.adults)
    return FlightsResponse(
        origin_airport=origin_ap.iata,
        arrival_airport=dest.airport,
        estimate=estimate,
        offers=offers,
        has_live_data=len(offers) > 0,
    )


@app.post("/api/fly-prices", response_model=FlyPricesResponse)
async def fly_prices(request: FlyPricesRequest):
    origin_ap = nearest_airport(request.origin.lat, request.origin.lng)
    routes: list[tuple[str, str]] = []
    for name in request.destinations:
        dest = next((d for d in FLY_DESTINATIONS if d.name == name), None)
        if dest is not None:
            routes.append((name, dest.airport))
    prices = await cheapest_prices(origin_ap.iata, routes, request.depart_date)
    return FlyPricesResponse(
        origin_airport=origin_ap.iata,
        prices={name: PriceSummary(**summary) for name, summary in prices.items()},
    )


@app.post("/api/flights/calendar", response_model=CalendarResponse)
async def flights_calendar(request: CalendarRequest):
    dest = next((d for d in FLY_DESTINATIONS if d.name == request.destination_name), None)
    if dest is None:
        raise HTTPException(
            status_code=422, detail=f"Unknown fly destination: {request.destination_name}"
        )
    origin_ap = nearest_airport(request.origin.lat, request.origin.lng)
    summary = await price_calendar(origin_ap.iata, dest.airport, request.depart_date)
    return CalendarResponse(
        origin_airport=origin_ap.iata,
        arrival_airport=dest.airport,
        currency=summary.get("currency", "USD"),
        starting_price=summary.get("starting_price"),
        cheapest_day=summary.get("cheapest_day"),
        days=summary.get("days", []),
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    return await refine(request)
