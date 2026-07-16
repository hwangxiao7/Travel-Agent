from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.agents.planner import (
    create_plan,
    plan_for_destination,
    plan_for_fly_destination,
    search_destinations,
)
from app.agents.refiner import refine
from app.auth import get_optional_user
from app.config import settings
from app.db import User, get_db, init_db
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
    ActivitiesRequest,
    ActivitiesResponse,
    ActivityVenuesRequest,
    ActivityVenuesResponse,
    ActivityVenueOut,
    DiscoverRequest,
    DiscoverResponse,
    SelectRequest,
    SelectResponse,
    SocialImportRequest,
    SocialImportResponse,
    SocialTextImportRequest,
)
from app.routers.account import router as account_router
from app.routers.assets import router as assets_router
from app.routers.auth_china import router as auth_china_router
from app.routers.beta import router as beta_router
from app.routers.likes import router as likes_router
from app.routers.taste import router as taste_router
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
from app.observability import atraced, setup_observability


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Spontaneous Travel Agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_observability(app)
app.include_router(account_router)
app.include_router(taste_router)
app.include_router(beta_router)
app.include_router(assets_router)
app.include_router(auth_china_router)
app.include_router(likes_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "destinations": len(DESTINATIONS)}


# --- collective-intelligence funnel logging (best-effort, never blocks) ------

def _intent_plan(preferences, trip_type: str) -> str:
    from app.services.interaction_log import intent_for_plan

    return intent_for_plan(preferences, trip_type)


def _log_shown(user, *, surface: str, intent_key: str, candidates: list[dict], kind: str) -> None:
    if user is None or not candidates:
        return
    from app.services.interaction_log import log_events

    events = [
        {
            "stage": "shown",
            "surface": surface,
            "intent_key": intent_key,
            "item_name": c.get("name", ""),
            "item_kind": kind,
        }
        for c in candidates[:5]
        if c.get("name")
    ]
    log_events(user, events)


def _log_activity_shown(user, request, acts) -> None:
    if user is None or not acts:
        return
    from app.services.interaction_log import intent_for_activities, log_events

    intent = intent_for_activities(request.energy, request.companion)
    events = [
        {
            "stage": "shown",
            "surface": "activities",
            "intent_key": intent,
            "item_key": a.key,
            "item_name": a.name_en,
            "item_kind": "activity",
        }
        for a in acts[:5]
    ]
    log_events(user, events)


def _log_selected(user, *, surface: str, item_key: str, item_name: str, kind: str) -> None:
    if user is None:
        return
    from app.services.interaction_log import log_event

    log_event(user, stage="selected", surface=surface,
              item_key=item_key, item_name=item_name, item_kind=kind)


@app.get("/api/geocode")
async def geocode_address(q: str):
    return {"results": await geocode(q)}


@app.post("/api/plan", response_model=PlanResponse)
async def plan_trip(
    request: PlanRequest,
    user: User | None = Depends(get_optional_user),
):
    async with atraced("/api/plan"):
        try:
            itinerary, candidates = await create_plan(request, user=user)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        _log_shown(
            user,
            surface="plan",
            intent_key=_intent_plan(request.preferences, request.trip_type),
            candidates=candidates,
            kind="destination",
        )
        return PlanResponse(itinerary=itinerary, candidates=candidates)


@app.post("/api/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    user: User | None = Depends(get_optional_user),
):
    try:
        itinerary, candidates, semantic, meta = await search_destinations(request, user=user)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _log_shown(
        user,
        surface="search",
        intent_key=_intent_plan(request.preferences, request.trip_type),
        candidates=candidates,
        kind="destination",
    )
    return SearchResponse(
        itinerary=itinerary,
        candidates=candidates,
        semantic=semantic,
        intent=meta.get("intent"),
        validation=meta.get("validation"),
        latency_ms=meta.get("latency_ms"),
        context_blocks=meta.get("context_blocks") or [],
        memory=meta.get("memory"),
        fusion_weights=meta.get("fusion_weights"),
        search_path=meta.get("search_path"),
    )


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


@app.post("/api/social/import", response_model=SocialImportResponse)
async def social_import(request: SocialImportRequest):
    """Compliant TikTok/social path: user submits post links, we distill facts.

    No scraping: each link is resolved via the platform's official oEmbed. We
    persist only verified place facts; the official embeds are returned for
    live display and never stored."""
    from app.services.social import import_from_links
    from app.services.trending_store import upsert_spots

    if not request.urls:
        raise HTTPException(status_code=422, detail="No links submitted")

    async with atraced("/api/social/import"):
        located, embeds = await import_from_links(
            request.urls, request.lat, request.lng, request.dest_name, request.language
        )
        created = updated = 0
        if request.persist and request.dest_name and located:
            created, updated = upsert_spots(request.dest_name, located)
        return SocialImportResponse(
            imported_links=len(embeds),
            spots=[place for place, _sources in located],
            embeds=embeds,
            created=created,
            updated=updated,
        )


@app.post("/api/social/import-text", response_model=SocialImportResponse)
async def social_import_text(request: SocialTextImportRequest):
    """Compliant path for platforms without oEmbed (e.g. Xiaohongshu/RED).

    The user pastes note text they copied themselves. We extract + verify place
    facts and persist only those; the pasted text is never stored."""
    from app.services.social import import_from_text
    from app.services.trending_store import upsert_spots

    if not request.texts:
        raise HTTPException(status_code=422, detail="No text submitted")

    async with atraced("/api/social/import-text"):
        located = await import_from_text(
            request.texts,
            request.lat,
            request.lng,
            request.dest_name,
            request.language,
            request.platform,
        )
        created = updated = 0
        if request.persist and request.dest_name and located:
            created, updated = upsert_spots(request.dest_name, located)
        return SocialImportResponse(
            imported_links=len(request.texts),
            spots=[place for place, _sources in located],
            embeds=[],
            created=created,
            updated=updated,
        )


@app.post("/api/discover", response_model=DiscoverResponse)
async def discover(
    request: DiscoverRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Persona-matched push of fresh trending experiences near the user.

    Not a nearby-places list: a spot is only pushed if it matches the user's
    taste persona (explicit interests/preferences + history)."""
    from app.services.discovery import recommend_experiences

    async with atraced("/api/discover"):
        pushes, persona_tags = await recommend_experiences(
            db,
            user,
            lat=request.origin.lat,
            lng=request.origin.lng,
            preferences=[p.value for p in request.preferences],
            interests=request.interests,
            radius_miles=request.radius_miles,
            language=request.language,
            k=request.k,
        )
        # Evolve the taste profile: remember what a signed-in user asked for.
        if user is not None and request.interests.strip():
            from app.services.taste_profile import record_snippet

            record_snippet(db, user, request.interests, source="interest", weight=0.6)
        return DiscoverResponse(pushes=pushes, persona_tags=persona_tags)


@app.post("/api/activities", response_model=ActivitiesResponse)
async def activities(
    request: ActivitiesRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Shop-independent activity ideas for 'don't know what to do today'.

    Pushes 娱乐项目 (types), ranked by taste + season + context — not merchants."""
    from app.services.activities import recommend_activities

    async with atraced("/api/activities"):
        acts = await recommend_activities(
            db,
            user,
            interests=request.interests,
            companion=request.companion,
            energy=request.energy,
            budget=request.budget,
            weather=request.weather,
            language=request.language,
            k=request.k,
        )
        _log_activity_shown(user, request, acts)
        return ActivitiesResponse(activities=acts)


@app.post("/api/activities/venues", response_model=ActivityVenuesResponse)
async def activity_venues(
    request: ActivityVenuesRequest,
    user: User | None = Depends(get_optional_user),
):
    """Given an activity type, find nearby concrete places to actually go.

    e.g. farmers_market → farmers markets; farm_animals → petting farm / zoo / cat cafe.
    """
    from app.services.activity_venues import resolve_venues

    async with atraced("/api/activities/venues"):
        try:
            activity, venues = await resolve_venues(
                request.activity_key,
                lat=request.origin.lat,
                lng=request.origin.lng,
                radius_miles=request.radius_miles,
                k=request.k,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        # Resolving venues for a picked activity is a strong interest signal.
        _log_selected(user, surface="venues", item_key=activity.key,
                      item_name=activity.name_en, kind="activity")
        zh = request.language.lower().startswith("zh")
        return ActivityVenuesResponse(
            activity_key=activity.key,
            activity_name=activity.name_zh if zh else activity.name_en,
            venues=[
                ActivityVenueOut(
                    name=v.name,
                    lat=v.lat,
                    lng=v.lng,
                    distance_miles=v.distance_miles,
                    drive_time=v.drive_time,
                    source=v.source,
                    query=v.query,
                    blurb=v.blurb,
                )
                for v in venues
            ],
        )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    return await refine(request)
