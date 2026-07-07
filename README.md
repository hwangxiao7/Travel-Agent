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
cp .env.example .env         # optional: VITE_MAPBOX_TOKEN for map
npm run dev
```

Open http://localhost:5173

## Environment

| Variable | Where | Purpose |
|---|---|---|
| `LLM_PROVIDER` | backend `.env` | `template` (default), `openai`, or `anthropic` |
| `OPENAI_API_KEY` | backend `.env` | GPT-4o-mini summaries & chat |
| `ANTHROPIC_API_KEY` | backend `.env` | Claude Haiku summaries & chat |
| `OPENWEATHER_API_KEY` | backend `.env` | Live weather note on plan |
| `VITE_MAPBOX_TOKEN` | frontend `.env` | Interactive map |

User preferences (home location, tags) persist in **browser localStorage** — no account required.

## API

- `POST /api/plan` — generate itinerary from constraints
- `POST /api/chat` — refine plan via conversation
- `GET /api/health` — health check

## MVP scope

- Day trip & weekend (2-day) planning
- Drive-time filtering from origin coordinates
- Preference tags: national park, hiking, city walk, forest, beach
- Hybrid UI: constraint panel + map + itinerary + chat

Not in v1: user accounts, bookings, multi-day flights, real-time fares.
