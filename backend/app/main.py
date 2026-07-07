from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.agents.planner import create_plan
from app.agents.refiner import refine
from app.config import settings
from app.models.schemas import ChatRequest, ChatResponse, PlanRequest, PlanResponse
from app.services.destinations import DESTINATIONS
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


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    return await refine(request)
