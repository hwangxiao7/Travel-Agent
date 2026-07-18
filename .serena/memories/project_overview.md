# Project Overview — 说走就走旅行助手 (Travel-Agent)

AI-driven North America "just go" travel planner. iOS is the primary product; Web is a beta.
A FastAPI backend runs an orchestration-style RAG Agent: retrieval decides *where to go*,
the LLM writes grounded *what to do*, hard constraints guarantee *the drive is feasible*.

## Two planning entry points
- Constraint planning `POST /api/plan`: preference chips only → `find_candidates` filters by
  feasible drive time → synthesized query → `rag_pipeline` re-rank → grounded generation.
- Natural-language search `POST /api/search`: free text (zh/en) → intent extraction → LLM
  activity phrase → semantic-gated dual path → grounded generation.

## Core design principle: graceful degradation
LLM, embeddings, weather, events, flights, and social are all optional. With zero API keys the
system still runs end-to-end via a curated catalog + keyword retrieval.

## Tech stack
- Backend: Python 3.10, FastAPI, Pydantic v2, SQLAlchemy 2, httpx, Uvicorn.
- Auth: email+password → JWT (SQLite by default, override `DATABASE_URL`). Phone OTP / WeChat
  OAuth modules exist but are OFF by default.
- LLM: OpenAI-compatible (`.env`); local Ollama / hosted / no-key tri-state. Embeddings can be local (PyTorch).
- RAG: hybrid retrieval (semantic + keyword), on-disk embedding cache, JSON grounded generation.
- Observability: OpenTelemetry tracing, Prometheus `/metrics`, structured JSON file logs.
- Frontend: React 19, Vite, TypeScript, Leaflet, hand-written CSS. i18n: English + Simplified Chinese.
- Map/geo (key-free): Nominatim, Overpass, OSRM, Leaflet.

## Canonical docs (read these before deep-diving code)
- `PROJECT_OVERVIEW.md` — main Chinese tech doc (architecture, RAG, API).
- `docs/项目现状与AI-Agent工程实践.md` — current status snapshot + feature list.
- `docs/架构技术选型.md` — tech choices and rationale.
- `docs/项目技术分析.md` — end-to-end technical analysis.
- `docs/CHANGELOG.md` — dated change log (newest first).
