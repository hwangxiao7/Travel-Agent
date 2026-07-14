from __future__ import annotations

import asyncio
from datetime import date, timedelta

from app.agents.grounded import (
    generate_grounded_days,
    grounding_context_used,
    validate_grounded_output,
)
from app.knowledge.corpus import context_for
from app.models.schemas import (
    Activity,
    DayPlan,
    Event,
    FlyPlanRequest,
    Itinerary,
    Place,
    PlanRequest,
    Preference,
    SearchRequest,
    SelectRequest,
    SocialPost,
)
from app.services.airports import airport_by_iata, nearest_airport
from app.services.constraint_engine import ScoredDestination, find_candidates
from app.services.destinations import DESTINATIONS
from app.services.events import fetch_events
from app.services.fly_destinations import FLY_DESTINATIONS
from app.services.flights import estimate_flight
from app.services.geo import estimate_drive_hours, format_duration, haversine_miles
from app.services.i18n import lang_name, pack, tr
from app.services.llm import fetch_weather_note, generate_summary
from app.services.places import fetch_nearby_places
from app.services.poi_search import PoiHit, search_nearby_pois
from app.services.query_understanding import has_focus_query
from app.services.rag_pipeline import corpus_has_semantic_focus
from app.services.rag_pipeline import rag_pipeline
from app.services.routing import drive_duration_hours, drive_durations_hours
from app.services.social import social_highlights
from app.services.trending_store import get_trending_places


def _packing_tips(prefs: list[Preference], trip_type: str, lang: str) -> list[str]:
    keys = ["water", "snacks", "charger"]
    tags = set(prefs)
    if Preference.HIKING in tags or Preference.NATIONAL_PARK in tags:
        keys.extend(["trail_shoes", "rain_layer", "sunscreen"])
    if Preference.BEACH in tags:
        keys.append("sandals")
    if trip_type == "weekend":
        keys.extend(["overnight", "toiletries", "warm_layer"])
    return [pack(k, lang) for k in keys]


def _activities_from_dest(scored: ScoredDestination, day_index: int) -> list[Activity]:
    dest = scored.destination
    rows = list(dest.day_activities)
    if day_index == 1 and dest.weekend_extra:
        rows.extend(dest.weekend_extra)
    return [Activity(time=t, place=p, duration=d, note=n) for t, p, d, n in rows]


async def _refine_drive_times(origin, scored_list: list[ScoredDestination]) -> None:
    """Replace haversine estimates with real OSRM road durations, in place.

    Best-effort: keeps the estimate for any entry OSRM can't route (or if the
    whole call fails)."""
    if not scored_list:
        return
    coords = [(s.destination.lat, s.destination.lng) for s in scored_list]
    hours_list = await drive_durations_hours(origin.lat, origin.lng, coords)
    if not hours_list:
        return
    for scored, hours in zip(scored_list, hours_list):
        if hours is not None:
            scored.drive_hours = hours
            scored.drive_time = format_duration(hours)


async def _social_for(
    name: str, lat: float, lng: float, language: str
) -> tuple[list[SocialPost], list[Place]]:
    """Serve trending spots from the ingested store; fall back to live scraping.

    Ingested spots are the durable, verified, cross-validated asset — so if the
    background pipeline has populated them we skip per-request scraping entirely
    (faster, cheaper, no live API dependency). When empty (destination never
    ingested), degrade to a live best-effort fetch so the demo still works."""
    spots = get_trending_places(name)
    if spots:
        return [], spots
    return await social_highlights(name, lat, lng, language)


async def _local_highlights(
    lat: float, lng: float, start_date: str
) -> tuple[list[Place], list[Place], list[Event]]:
    """Fetch nearby food + fun (OSM) and events (Ticketmaster) concurrently.

    Each source is best-effort and degrades to empty on failure/no key."""
    (food, fun), events = await asyncio.gather(
        fetch_nearby_places(lat, lng),
        fetch_events(lat, lng, start_date),
    )
    return food, fun, events


async def _apply_grounding(
    itinerary: Itinerary,
    request: PlanRequest | SelectRequest | FlyPlanRequest | SearchRequest,
    food: list[Place],
    fun: list[Place],
    events: list[Event],
    profile_note: str = "",
    rag_context: str = "",
    framing_note: str = "",
) -> Itinerary:
    """RAG step: replace catalog activities with LLM-generated, grounded ones.

    `rag_context` is multi-doc retrieval (top destinations + user memory) from
    the search/plan pipeline — not just the single destination blurb.
    `framing_note` carries local-discovery vibe (mood / energy / company).
    """
    base_ctx = context_for(itinerary.destination)
    merged = grounding_context_used(base_ctx, rag_context)
    grounded = await generate_grounded_days(
        destination=itinerary.destination,
        region="",
        highlight=itinerary.summary,
        context=base_ctx,
        base_days=itinerary.days,
        nearby_food=food,
        nearby_fun=fun,
        events=events,
        weather_note=itinerary.weather_note,
        preferences=[p.value for p in request.preferences],
        language=request.language,
        profile_note=profile_note,
        rag_context=rag_context,
        framing_note=framing_note,
    )
    if grounded:
        known = {p.name for p in food + fun}
        check = validate_grounded_output(
            grounded,
            known_places=known,
            context=merged or base_ctx or "",
        )
        if check.get("ok", True):
            return itinerary.model_copy(update={"days": grounded})
    return itinerary


def _rag_context_text(blocks: list[str] | None, *, limit: int = 4) -> str:
    if not blocks:
        return ""
    return "\n\n".join(b for b in blocks[:limit] if b)


def _framing_note(intent) -> str:
    """Human-readable local-discovery vibe from intent (mood/energy/company/time)."""
    if intent is None:
        return ""
    bits: list[str] = []
    if getattr(intent, "mood", None):
        bits.append("mood " + "/".join(intent.mood[:3]))
    if getattr(intent, "energy_level", None):
        bits.append(f"{intent.energy_level} energy")
    if getattr(intent, "social_context", None):
        bits.append(f"for {intent.social_context}")
    if getattr(intent, "time_window", None):
        bits.append(str(intent.time_window))
    return ", ".join(bits)


def _synthetic_plan_query(request: PlanRequest, profile_text: str = "") -> str:
    """Build an embeddable query when the user only picked preference chips."""
    prefs = [p.value.replace("-", " ") for p in request.preferences]
    bits = [f"{request.trip_type.replace('-', ' ')} near me"]
    if prefs:
        bits.append("looking for " + ", ".join(prefs))
    else:
        bits.append("outdoor day trip destinations")
    bits.append(f"within {request.max_drive_hours:g} hours drive")
    if profile_text and "none yet" not in profile_text.lower():
        bits.append("traveler likes: " + profile_text[:200])
    return ". ".join(bits)


def _build_itinerary(
    request: PlanRequest,
    scored: ScoredDestination,
    alternatives: list[str],
    weather_note: str,
    summary: str,
    nearby_food: list[Place] | None = None,
    nearby_fun: list[Place] | None = None,
    events: list[Event] | None = None,
) -> Itinerary:
    start = date.fromisoformat(request.start_date)
    days: list[DayPlan] = []

    if request.trip_type == "weekend":
        end = date.fromisoformat(request.end_date or (start + timedelta(days=1)).isoformat())
        day_count = (end - start).days + 1
        day_count = min(max(day_count, 2), 2)
        for i in range(day_count):
            d = start + timedelta(days=i)
            days.append(DayPlan(date=d.isoformat(), activities=_activities_from_dest(scored, i)))
    else:
        days.append(DayPlan(date=start.isoformat(), activities=_activities_from_dest(scored, 0)))

    return Itinerary(
        destination=scored.destination.name,
        destination_lat=scored.destination.lat,
        destination_lng=scored.destination.lng,
        drive_time=scored.drive_time,
        drive_hours=scored.drive_hours,
        days=days,
        alternatives=alternatives,
        packing_tips=_packing_tips(request.preferences, request.trip_type, request.language),
        weather_note=weather_note,
        summary=summary,
        nearby_food=nearby_food or [],
        nearby_fun=nearby_fun or [],
        events=events or [],
    )


async def create_plan(
    request: PlanRequest, user=None
) -> tuple[Itinerary, list[dict]]:
    from app.observability import atraced

    async with atraced("planner.create_plan"):
        candidates = find_candidates(request)
        if not candidates:
            raise ValueError(
                "No destinations match your drive-time limit. Try increasing max drive hours or broadening preferences."
            )

        profile_note = ""
        memory_ctx = None
        persona = None
        db = None
        if user is not None:
            from app.db import SessionLocal, get_engine
            from app.services.persona import get_or_build_persona
            from app.services.personalization import rebuild_profile_text
            from app.services.user_memory import retrieve_user_memories

            get_engine()
            assert SessionLocal is not None
            db = SessionLocal()
            try:
                profile_note = rebuild_profile_text(db, user)
                synth = _synthetic_plan_query(request, profile_note)
                memory_ctx = await retrieve_user_memories(db, user, synth, k=5)
                persona = get_or_build_persona(db, user)
            finally:
                # Keep session closed; memory_ctx is in-memory after retrieve.
                db.close()
                db = None

        # RAG re-rank over drive-feasible candidates (amplifies RAG on chip-only path).
        synth_query = _synthetic_plan_query(request, profile_note)
        rag = await rag_pipeline.run(
            query=synth_query,
            origin_lat=request.origin.lat,
            origin_lng=request.origin.lng,
            max_drive_hours=request.max_drive_hours,
            max_flight_hours=request.max_flight_hours,
            allow_flight=request.allow_flight,
            preferences=[p.value for p in request.preferences],
            profile_text=profile_note,
            memory_ctx=memory_ctx,
            k=max(8, len(candidates)),
            start_date=request.start_date,
            persona=persona,
        )
        by_name = {c.destination.name: c for c in candidates}
        reranked: list[ScoredDestination] = []
        for ranked in rag.ranked:
            base = by_name.get(ranked.doc.dest_name)
            if base is None:
                continue
            # Blend catalog feasibility score with RAG final score.
            base.score = 0.45 * base.score + 0.55 * (ranked.scores.final_score * 10)
            # Carry human explanation onto the candidate payload later.
            setattr(base, "_rag_explanation", ranked.scores.explanation)
            setattr(base, "_rag_highlight", ranked.doc.highlight or base.destination.highlight)
            reranked.append(base)
        # Keep any feasible destinations RAG dropped (e.g. embedding miss) at the end.
        seen = {c.destination.name for c in reranked}
        for c in candidates:
            if c.destination.name not in seen:
                reranked.append(c)
        if reranked:
            candidates = reranked
            candidates.sort(key=lambda c: c.score, reverse=True)

        await _refine_drive_times(request.origin, candidates)
        top = candidates[0]
        alts = [c.destination.name for c in candidates[1:3]]
        weather, (food, fun, events), (guides, viral) = await asyncio.gather(
            fetch_weather_note(top.destination.lat, top.destination.lng, request.language),
            _local_highlights(top.destination.lat, top.destination.lng, request.start_date),
            _social_for(
                top.destination.name, top.destination.lat, top.destination.lng, request.language
            ),
        )

        rag_ctx = _rag_context_text(rag.context_blocks)
        summary_prompt = (
            f"Write 2-3 sentences for a spontaneous trip plan.\n"
            f"Origin: {request.origin.label or 'user location'}\n"
            f"Destination: {top.destination.name} ({top.destination.highlight})\n"
            f"Drive: {top.drive_time}\n"
            f"Trip type: {request.trip_type}\n"
            f"Preferences: {', '.join(p.value for p in request.preferences) or 'general outdoor'}\n"
            f"Weather: {weather}\n"
            f"{('Traveler history: ' + profile_note) if profile_note else ''}\n"
            f"{('Retrieved context: ' + rag_ctx[:500]) if rag_ctx else ''}\n"
            f"Tone: enthusiastic but practical.\n"
            f"Respond in {lang_name(request.language)}. Keep place names in English."
        )
        summary = await generate_summary(summary_prompt)
        if not summary:
            summary = tr(
                "summary_fallback",
                request.language,
                name=top.destination.name,
                highlight=top.destination.highlight,
                time=top.drive_time,
            )

        itinerary = _build_itinerary(request, top, alts, weather, summary, food, fun, events)
        itinerary = await _apply_grounding(
            itinerary,
            request,
            food,
            fun,
            events,
            profile_note=profile_note,
            rag_context=rag_ctx,
            framing_note=_framing_note(getattr(rag, "intent", None)),
        )
        itinerary = itinerary.model_copy(update={"guides": guides, "viral": viral})
        candidate_payload = [
            {
                "name": c.destination.name,
                "lat": c.destination.lat,
                "lng": c.destination.lng,
                "drive_time": c.drive_time,
                "drive_hours": c.drive_hours,
                "score": round(c.score, 2),
                "highlight": getattr(c, "_rag_highlight", None) or c.destination.highlight,
                "explanation": getattr(c, "_rag_explanation", None) or "",
            }
            for c in candidates
        ]
        return itinerary, candidate_payload


async def plan_for_destination(
    req: SelectRequest,
    *,
    rag_context: str = "",
    profile_note: str = "",
    framing_note: str = "",
) -> Itinerary:
    dest = next((d for d in DESTINATIONS if d.name == req.destination_name), None)
    if dest is None:
        raise ValueError(f"Unknown destination: {req.destination_name}")

    miles = haversine_miles(req.origin.lat, req.origin.lng, dest.lat, dest.lng)
    real_hours = await drive_duration_hours(req.origin.lat, req.origin.lng, dest.lat, dest.lng)
    hours = real_hours if real_hours is not None else estimate_drive_hours(miles)
    scored = ScoredDestination(
        destination=dest,
        distance_miles=round(miles, 1),
        drive_hours=round(hours, 2),
        drive_time=format_duration(hours),
        score=0.0,
    )

    plan_req = PlanRequest(
        origin=req.origin,
        trip_type=req.trip_type,
        start_date=req.start_date,
        end_date=req.end_date,
        max_drive_hours=8.0,
        max_flight_hours=3.0,
        preferences=req.preferences,
        allow_flight=req.trip_type == "weekend",
        language=req.language,
    )
    alts = [c.destination.name for c in find_candidates(plan_req, limit=4) if c.destination.name != dest.name][:2]
    weather, (food, fun, events), (guides, viral) = await asyncio.gather(
        fetch_weather_note(dest.lat, dest.lng, req.language),
        _local_highlights(dest.lat, dest.lng, req.start_date),
        _social_for(dest.name, dest.lat, dest.lng, req.language),
    )

    summary_prompt = (
        f"Write 2-3 sentences for a spontaneous trip plan.\n"
        f"Origin: {req.origin.label or 'user location'}\n"
        f"Destination: {dest.name} ({dest.highlight})\n"
        f"Drive: {scored.drive_time}\n"
        f"Trip type: {req.trip_type}\n"
        f"Weather: {weather}\n"
        f"Tone: enthusiastic but practical.\n"
        f"Respond in {lang_name(req.language)}. Keep place names in English."
    )
    summary = await generate_summary(summary_prompt)
    if not summary:
        summary = tr(
            "summary_fallback",
            req.language,
            name=dest.name,
            highlight=dest.highlight,
            time=scored.drive_time,
        )

    itinerary = _build_itinerary(plan_req, scored, alts, weather, summary, food, fun, events)
    itinerary = await _apply_grounding(
        itinerary,
        req,
        food,
        fun,
        events,
        profile_note=profile_note,
        rag_context=rag_context,
        framing_note=framing_note,
    )
    return itinerary.model_copy(update={"guides": guides, "viral": viral})


async def plan_for_fly_destination(
    req: FlyPlanRequest,
    *,
    rag_context: str = "",
    profile_note: str = "",
    framing_note: str = "",
) -> Itinerary:
    dest = next((d for d in FLY_DESTINATIONS if d.name == req.destination_name), None)
    if dest is None:
        raise ValueError(f"Unknown fly destination: {req.destination_name}")

    origin_ap = nearest_airport(req.origin.lat, req.origin.lng)
    dest_ap = airport_by_iata(dest.airport)
    est = estimate_flight(origin_ap, dest_ap) if dest_ap else {"flight_hours": 0.0, "flight_time": ""}

    scored = ScoredDestination(
        destination=dest,  # type: ignore[arg-type]  # duck-typed: same shape as Destination
        distance_miles=est.get("distance_miles", 0),
        drive_hours=est["flight_hours"],
        drive_time=est["flight_time"],
        score=0.0,
    )

    plan_req = PlanRequest(
        origin=req.origin,
        trip_type=req.trip_type,
        start_date=req.start_date,
        end_date=req.end_date,
        max_drive_hours=8.0,
        max_flight_hours=8.0,
        preferences=req.preferences,
        allow_flight=True,
        language=req.language,
    )
    weather, (food, fun, events), (guides, viral) = await asyncio.gather(
        fetch_weather_note(dest.lat, dest.lng, req.language),
        _local_highlights(dest.lat, dest.lng, req.start_date),
        _social_for(dest.name, dest.lat, dest.lng, req.language),
    )

    summary_prompt = (
        f"Write 2-3 sentences for a spontaneous fly-away trip plan.\n"
        f"Fly from {origin_ap.iata} to {dest.name} ({dest.highlight})\n"
        f"Flight: about {est['flight_time']}\n"
        f"Trip type: {req.trip_type}\n"
        f"Weather: {weather}\n"
        f"Tone: enthusiastic but practical.\n"
        f"Respond in {lang_name(req.language)}. Keep place names in English."
    )
    summary = await generate_summary(summary_prompt)
    if not summary:
        summary = tr(
            "fly_summary_fallback",
            req.language,
            name=dest.name,
            highlight=dest.highlight,
            time=est["flight_time"],
            airport=origin_ap.iata,
        )

    itinerary = _build_itinerary(plan_req, scored, [], weather, summary, food, fun, events)
    itinerary = await _apply_grounding(
        itinerary,
        req,
        food,
        fun,
        events,
        profile_note=profile_note,
        rag_context=rag_context,
        framing_note=framing_note,
    )
    return itinerary.model_copy(
        update={
            "travel_mode": "fly",
            "origin_airport": origin_ap.iata,
            "destination_airport": dest.airport,
            "guides": guides,
            "viral": viral,
        }
    )


async def plan_for_poi(
    req: SearchRequest,
    hit: PoiHit,
    alternatives: list[str],
) -> Itinerary:
    """Build a day plan around a live POI hit (secondary search path)."""
    weather, (food, fun, events) = await asyncio.gather(
        fetch_weather_note(hit.lat, hit.lng, req.language),
        _local_highlights(hit.lat, hit.lng, req.start_date),
    )
    summary_prompt = (
        f"Write 2-3 sentences for a spontaneous trip focused on this place.\n"
        f"Origin: {req.origin.label or 'user location'}\n"
        f"Place: {hit.name}\n"
        f"Why: {hit.highlight}\n"
        f"Drive: {hit.drive_time}\n"
        f"User asked: {req.query}\n"
        f"Weather: {weather}\n"
        f"Tone: practical and specific to the activity the user asked for.\n"
        f"Respond in {lang_name(req.language)}. Keep place names in English."
    )
    summary = await generate_summary(summary_prompt)
    if not summary:
        summary = (
            f"Head to {hit.name} ({hit.drive_time} away) for “{req.query}”. "
            f"{hit.highlight}"
        )

    start = date.fromisoformat(req.start_date)
    activities = [
        Activity(
            time="10:00",
            place=hit.name,
            duration="2–3h",
            note=hit.highlight or f"Main stop for: {req.query}",
        ),
    ]
    if food:
        activities.append(
            Activity(
                time="13:00",
                place=food[0].name,
                duration="1h",
                note=food[0].note or "Nearby food stop",
            )
        )
    if fun:
        activities.append(
            Activity(
                time="15:00",
                place=fun[0].name,
                duration="1h",
                note=fun[0].note or "Extra nearby stop",
            )
        )
    days = [DayPlan(date=start.isoformat(), activities=activities)]
    if req.trip_type == "weekend":
        end = date.fromisoformat(req.end_date or (start + timedelta(days=1)).isoformat())
        days.append(
            DayPlan(
                date=end.isoformat(),
                activities=[
                    Activity(
                        time="10:00",
                        place=hit.name,
                        duration="2h",
                        note="Return visit / second session if available.",
                    )
                ],
            )
        )

    return Itinerary(
        destination=hit.name,
        destination_lat=hit.lat,
        destination_lng=hit.lng,
        drive_time=hit.drive_time,
        drive_hours=round(hit.drive_hours, 2),
        days=days,
        alternatives=alternatives,
        packing_tips=_packing_tips(req.preferences, req.trip_type, req.language),
        weather_note=weather,
        summary=summary,
        nearby_food=food or [],
        nearby_fun=fun or [],
        events=events or [],
    )


def _corpus_has_focus_hit(ranked, intent) -> bool:
    """Semantic gate: embedding similarity to LLM activity phrase, not keywords."""
    if not has_focus_query(intent) or not ranked:
        return False
    return corpus_has_semantic_focus(ranked)


async def search_destinations(
    req: SearchRequest, user=None
) -> tuple[Itinerary, list[dict], bool, dict]:
    """Two-path search:
    1) Curated corpus RAG (LLM rewrite + embedding similarity)
    2) Nearby POI place-search (when corpus semantic score is too low)
    """
    from app.services.query_understanding import (
        apply_intent_to_request_fields,
        extract_intent,
        has_focus_query,
    )

    intent = extract_intent(req.query)
    apply_intent_to_request_fields(intent, req)

    ui_prefs = [p.value for p in req.preferences]
    if has_focus_query(intent):
        ranking_prefs: list[str] = list(intent.preferences)
    else:
        ranking_prefs = list(dict.fromkeys([*intent.preferences, *ui_prefs]))

    profile_text = ""
    memory_ctx = None
    persona = None
    db = None
    if user is not None:
        from app.db import SessionLocal, get_engine
        from app.services.persona import get_or_build_persona
        from app.services.user_memory import retrieve_user_memories

        get_engine()
        assert SessionLocal is not None
        db = SessionLocal()
        memory_ctx = await retrieve_user_memories(db, user, req.query, k=5)
        persona = get_or_build_persona(db, user)
        profile = memory_ctx.profile
        profile_text = profile.profile_text
        if not has_focus_query(intent) and not ranking_prefs and profile.activity_preferences:
            ranking_prefs = list(profile.activity_preferences)
        if intent.pace is None and profile.travel_pace:
            intent.pace = profile.travel_pace

    try:
        rag = await rag_pipeline.run(
            query=req.query,
            origin_lat=req.origin.lat,
            origin_lng=req.origin.lng,
            max_drive_hours=req.max_drive_hours,
            max_flight_hours=req.max_flight_hours,
            allow_flight=req.allow_flight,
            preferences=ranking_prefs,
            profile_text=profile_text,
            memory_ctx=memory_ctx,
            k=8,
            intent=intent,
            start_date=req.start_date,
            persona=persona,
        )
    finally:
        if db is not None:
            db.close()

    # Path B: free-text focus missed the curated corpus → nearby POI search.
    use_poi = has_focus_query(intent) and not _corpus_has_focus_hit(rag.ranked, intent)
    if use_poi:
        pois = await search_nearby_pois(
            query=req.query,
            intent=intent,
            origin_lat=req.origin.lat,
            origin_lng=req.origin.lng,
            max_drive_hours=req.max_drive_hours,
            limit=8,
        )
        if pois:
            alts = [p.name for p in pois[1:4]]
            itinerary = await plan_for_poi(req, pois[0], alts)
            candidate_payload = [p.to_candidate_dict() for p in pois]
            meta = {
                "intent": intent.to_dict(),
                "validation": {
                    "has_results": True,
                    "search_path": "poi",
                    "corpus_focus_miss": True,
                },
                "latency_ms": rag.latency_ms,
                "context_blocks": [
                    f"[poi] {p.name}: {p.highlight}" for p in pois[:3]
                ],
                "memory": rag.memory,
                "fusion_weights": rag.fusion_weights,
                "search_path": "poi",
            }
            return itinerary, candidate_payload, False, meta

    if not rag.ranked:
        # A vague idea must never dead-end: widen the range once and retry so we
        # still surface the closest options rather than erroring out.
        rag = await rag_pipeline.run(
            query=req.query,
            origin_lat=req.origin.lat,
            origin_lng=req.origin.lng,
            max_drive_hours=max(req.max_drive_hours, 8.0),
            max_flight_hours=max(req.max_flight_hours, 6.0),
            allow_flight=True,
            preferences=ranking_prefs,
            profile_text=profile_text,
            memory_ctx=memory_ctx,
            k=8,
            intent=intent,
            start_date=req.start_date,
            persona=persona,
        )
        if not rag.ranked:
            raise ValueError("No destinations available yet — try widening your range.")

    # Free-text "idea" queries (e.g. "somewhere with forest and creek") must NOT
    # dead-end just because they don't hit a keyword or a Nominatim place name.
    # When there's no strong focus hit, fall through to the closest semantic
    # matches and tell the user they're approximate. Ranking already prevents
    # irrelevant park-spam, so the top result is the best-fitting real place.
    approx = has_focus_query(intent) and not _corpus_has_focus_hit(rag.ranked, intent)

    top_doc = rag.ranked[0].doc
    rag_ctx = _rag_context_text(rag.context_blocks)
    profile_for_ground = profile_text
    framing = _framing_note(intent)
    if approx:
        framing = (
            (framing + " ") if framing else ""
        ) + "No exact match for the request; present these as the closest nearby options and say so briefly."
    if top_doc.travel_mode == "fly":
        itinerary = await plan_for_fly_destination(
            FlyPlanRequest(
                origin=req.origin,
                destination_name=top_doc.dest_name,
                trip_type=req.trip_type,
                start_date=req.start_date,
                end_date=req.end_date,
                preferences=req.preferences,
                language=req.language,
            ),
            rag_context=rag_ctx,
            profile_note=profile_for_ground,
            framing_note=framing,
        )
    else:
        itinerary = await plan_for_destination(
            SelectRequest(
                origin=req.origin,
                destination_name=top_doc.dest_name,
                trip_type=req.trip_type,
                start_date=req.start_date,
                end_date=req.end_date,
                preferences=req.preferences,
                language=req.language,
            ),
            rag_context=rag_ctx,
            profile_note=profile_for_ground,
            framing_note=framing,
        )

    real_hours = await drive_durations_hours(
        req.origin.lat,
        req.origin.lng,
        [(r.doc.lat, r.doc.lng) for r in rag.ranked],
    )
    candidate_payload: list[dict] = []
    for idx, ranked in enumerate(rag.ranked):
        hours = estimate_drive_hours(
            haversine_miles(req.origin.lat, req.origin.lng, ranked.doc.lat, ranked.doc.lng)
        )
        if real_hours and idx < len(real_hours) and real_hours[idx] is not None:
            hours = real_hours[idx]
        candidate_payload.append(
            ranked.to_candidate_dict(
                drive_time=format_duration(hours),
                drive_hours=round(hours, 2),
            )
        )

    search_path = "corpus-approx" if approx else "corpus"
    meta = {
        "intent": rag.intent.to_dict(),
        "validation": {**(rag.validation or {}), "search_path": search_path, "approximate": approx},
        "latency_ms": rag.latency_ms,
        "context_blocks": rag.context_blocks,
        "memory": rag.memory,
        "fusion_weights": rag.fusion_weights,
        "search_path": search_path,
    }
    return itinerary, candidate_payload, rag.semantic, meta
