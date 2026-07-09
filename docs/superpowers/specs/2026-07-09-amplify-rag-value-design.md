# Amplify RAG Value — Design (2026-07-09)

## Goal
Make retrieval actually shape itineraries and be visible to users — not only rank candidates.

## Phase A (this change)

### 1. Retrieval → generation closed loop
- `rag_pipeline.run` already builds `context_blocks` (top docs + memory).
- Pass those blocks into `generate_grounded_days` via `_apply_grounding(rag_context=...)`.
- `search_destinations` and `create_plan` both feed retrieved context + traveler memory into grounding.
- Validation uses the same expanded context (not only the single destination blurb).

### 2. Visible “why this pick”
- Candidate cards show a short human reason from `explanation` (no 搜/广/推 scores).
- Prefer explanation over raw highlight when present.

### 3. `/api/plan` uses RAG re-rank
- Keep `find_candidates` for drive-time feasibility.
- Build a synthetic query from trip type + preference chips (+ profile when logged in).
- Re-rank with `rag_pipeline.run`; ground the top plan with retrieved context.

## Out of scope (later)
- Enriching corpus with OSM/TikTok/reviews (Phase B).
- Overpass-tag POI path (separate from RAG amplification).
- Exposing raw fusion weights in UI.

## Success criteria
- Search for「冲浪」: itinerary grounding prompt includes Santa Cruz corpus (+ related) blocks, not only one highlight string.
- Empty search box + beach chip: ranking influenced by RAG semantic scores.
- Candidate list shows a one-line “why” without score dumps.
