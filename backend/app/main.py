from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.agents.planner import create_plan
from app.config import settings
from app.models.schemas import ChatRequest, ChatResponse, PlanRequest, PlanResponse
from app.services.constraint_engine import find_candidates
from app.services.destinations import DESTINATIONS
from app.services.llm import chat_reply

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


@app.post("/api/plan", response_model=PlanResponse)
async def plan_trip(request: PlanRequest):
    try:
        itinerary, candidates = await create_plan(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PlanResponse(itinerary=itinerary, candidates=candidates)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    ctx = ""
    if request.current_itinerary:
        it = request.current_itinerary
        ctx = f"Current plan: {it.destination}, drive {it.drive_time}. Summary: {it.summary}"
    if request.origin:
        ctx += f" Origin: {request.origin.label} ({request.origin.lat}, {request.origin.lng})."

    history = "\n".join(f"{m.role}: {m.content}" for m in request.messages[-6:])
    prompt = (
        "You are a spontaneous North America travel agent assistant.\n"
        "Help refine day-trip or weekend plans. Be concise and actionable.\n"
        f"{ctx}\n\nConversation:\n{history}\n\nReply to the latest user message."
    )
    reply = await chat_reply(prompt)
    return ChatResponse(reply=reply, itinerary=request.current_itinerary)
