# Code Map — feature → files (where to look, don't re-scan)

Layering: **agents (orchestration) → services (retrieval & integrations) → curated catalog / SQLite.**
Use Serena symbol tools (`find_symbol`, `find_referencing_symbols`, `get_symbols_overview`) on the
files below instead of reading whole directories.

## Backend (`backend/app/`)
- `main.py` — FastAPI app + route wiring. Start here to find any HTTP endpoint.
- `config.py` — settings / feature flags / env parsing.
- `db.py`, `auth.py` — SQLAlchemy engine/session; JWT auth helpers.
- `observability.py` — OTel tracing + Prometheus metrics setup.
- `models/schemas.py` — Pydantic request/response schemas (the API contract).

### Agents (orchestration)
- `agents/planner.py` — `create_plan`, `search_destinations`, `plan_for_destination/fly/poi`.
- `agents/grounded.py` — `generate_grounded_days` (retrieval facts → day-by-day JSON) + `validate_grounded_output`.
- `agents/refiner.py` — chat refinement (rule-intent first, else RAG + LLM).
- `agents/ingest.py`, `agents/seed_experiences.py` — experience ingestion / seeding.

### RAG & retrieval (services/)
- `rag_pipeline.py` — full RAG: retrieve · score · 搜/广/推 fusion. **Core of `/api/plan` & `/api/search`.**
- `query_understanding.py` — NLP intent + LLM activity-phrase rewrite (open-vocabulary, no synonym table).
- `retrieval.py`, `rerank.py` — retrieval primitives + optional local rerank.
- `embeddings.py`, `local_embeddings.py` — embedding API + disk cache + local PyTorch backend.
- `knowledge/corpus.py` — destination → RAG documents (closed-domain plannable targets).
- `poi_search.py`, `places.py`, `geocode.py`, `geo.py` — Nominatim/Overpass POI fallback path.
- `destinations.py`, `fly_destinations.py`, `airports.py` — curated drive/fly catalogs.
- `routing.py` — OSRM real drive-time.
- `constraint_engine.py`, `trip_scope.py` — hard feasibility constraints.

### Personalization & crowd signals
- `user_memory.py` — retrieve trip/review memories into RAG context.
- `taste_profile.py`, `personalization.py`, `persona.py` — single-user taste vector / persona.
- `likes.py` (service) + `routers/likes.py` — double-tap like → batch into RAG.
- `interaction_log.py`, `crowd.py`, `signals.py` — funnel `InteractionEvent` + nightly `CrowdSignal` (P3: not yet in ranking).

### External integrations (all best-effort / optional)
- `llm.py` — LLM provider abstraction (OpenAI/Anthropic/template/Ollama).
- `events.py` (Ticketmaster), `flights.py`/`flights_api.py`, `social.py`/`reddit_source.py`/`oembed.py` (TikTok/social),
  `activities.py`/`activity*.py`/`experiences.py`, `discovery.py`, `trending_store.py`, `notify.py` (low-score email alerts).

### Assets & i18n
- `assets.py` + `routers/assets.py` + `asset_vibes.py` — vibe stickers, in-package compression + LRU + `/api/assets`.
- `i18n.py` — server-side i18n.

### Routers (`routers/`)
- `account.py`, `auth_china.py` (phone OTP / WeChat), `taste.py`, `likes.py`, `beta.py`, `assets.py`.

### Eval
- `eval/run_eval.py` — RAG eval (intent extraction, ranking P/R, constraint feasibility). Run: `python -m app.eval.run_eval`.

## Frontend (`frontend/src/`)
- `App.tsx`, `main.tsx` — root; unified entry: has search term → search, else plan.
- `api/client.ts`, `api/endpoints.ts`, `types.ts` — HTTP client + typed endpoints + shared types.
- `components/`: `SurprisePanel.tsx`, `PlannerPanel.tsx`, `CandidatesAccordion.tsx` (highlight + human-readable
  "推荐理由"), `AccountModal.tsx`, `BetaFeedback.tsx`, `ModeSwitcher.tsx`, `AssetImg.tsx`.
- `likes.ts`, `i18n.tsx` — client like state + i18n.

## iOS (`ios/TravelAgent/`)
- `ContentView.swift` — primary SwiftUI product surface.

## Key data flow (RAG)
NL/synthesized query → `query_understanding` → LLM activity phrase → `rag_pipeline.run`
→ semantic gate: corpus similar enough? → Path A `corpus` + `plan_for_*` + grounded, else
Path B `poi_search` (Nominatim) + `plan_for_poi` → `context_blocks` (top docs + user memory)
injected into `generate_grounded_days` → candidate cards show human-readable reason.
