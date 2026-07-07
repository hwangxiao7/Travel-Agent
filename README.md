# Spontaneous Travel Agent

Web AI agent for **spontaneous North America trips** — day trips and weekends based on your location, preferences, and drive-time limits.

## Stack

- **Frontend:** React + Vite + TypeScript
- **Backend:** Python FastAPI
- **Architecture:** Constraint engine (Python) filters destinations → LLM writes the narrative (optional)

## Quick start

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # edit keys as needed
uvicorn app.main:app --reload --port 8000
```

Works **without API keys** using a curated destination catalog and template summaries. Set `LLM_PROVIDER=openai` or `anthropic` plus the matching API key for AI summaries and chat.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

The map uses free OpenStreetMap tiles via Leaflet — no token or signup needed.

Open http://localhost:5173

## Environment

| Variable | Where | Purpose |
|---|---|---|
| `LLM_PROVIDER` | backend `.env` | `template` (default), `openai`, or `anthropic` |
| `OPENAI_API_KEY` | backend `.env` | GPT-4o-mini summaries & chat |
| `ANTHROPIC_API_KEY` | backend `.env` | Claude Haiku summaries & chat |
| `OPENWEATHER_API_KEY` | backend `.env` | Live weather note on plan |
| `AMADEUS_API_KEY` / `AMADEUS_API_SECRET` | backend `.env` | Live flight search (fares + times). Free key from [developers.amadeus.com](https://developers.amadeus.com) |

**Flights:** turn on the weekend flight toggle to see fly-to outdoor destinations (Zion, Grand Canyon, Yellowstone, Banff…) with estimated flight times. Add Amadeus keys for real fares and schedules — without them it gracefully shows estimates only.

The interactive map uses **Leaflet + OpenStreetMap** — free, no token required.

User preferences (home location, tags) persist in **browser localStorage** — no account required.

## API

- `POST /api/plan` — generate itinerary from constraints
- `POST /api/select` — build itinerary for a chosen drive candidate
- `POST /api/fly-destinations` — list fly-to destinations within a flight-time limit
- `POST /api/fly-plan` — build itinerary for a chosen fly-to destination
- `POST /api/flights` — search real/estimated flights (origin → destination, date)
- `POST /api/chat` — refine plan via conversation
- `POST /api/geocode` — address → coordinates
- `GET /api/health` — health check

## MVP scope

- Day trip & weekend (2-day) planning
- Drive-time filtering from origin coordinates
- Fly-to weekend destinations with estimated/real flight search (Amadeus)
- Preference tags: national park, hiking, city walk, forest, beach
- Hybrid UI: constraint panel + map + itinerary + chat
- Multi-language UI + AI responses (English / 中文, toggle in top bar)

Not in v1: user accounts, bookings, 3–5 day long trips.
