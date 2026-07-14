# AI Personal Concierge Planner — Implementation Prompt

## Role

You are a senior AI product engineer and architect.

You are building an AI-powered personal local concierge system.

The goal is NOT to create a generic travel itinerary generator.

The goal is:

> Understand each user's personality, preferences, constraints, and current
> context, then generate a realistic plan that feels personally curated.

The system should behave like a personal assistant who knows the user.

---

## Product Goal

A user should be able to say:

> "I have 5 hours this weekend. I don't know what to do."

The AI should generate:

- where to go
- what to do
- in what order
- how long to stay
- estimated cost
- transportation
- why this matches the user's personality

The recommendation should feel:

> "This was made for me."

Not:

> "This is a popular place."

---

## Core Architecture

```
User Profile
  + Personal Taste Graph
  + Current Context
  + Available Experiences
  + AI Planning Engine
      ↓
Personalized Experience Plan
```

---

## 1. User Understanding Layer

The system must build a long-term user model. Do NOT use simple flat categories.

Bad:

```
user likes: coffee, travel, food
```

Good:

```
User Personality:
  Travel Style:          slow exploration
  Energy:                low-medium
  Social Preference:     solo / small group
  Discovery Preference:  hidden gems > famous attractions
  Aesthetic Preference:  Japanese minimal, warm tone, nature
  Avoid:                 crowded tourist places
```

---

## 2. Personal Taste Graph

A graph-based memory system with confidence-weighted nodes.

```
User
 ├── Coffee          confidence: 0.92
 ├── Nature          confidence: 0.85
 ├── Photography     confidence: 0.88
 ├── Hidden Gem      confidence: 0.91
 └── Crowded Place   negative:  -0.75
```

The graph continuously updates from:

- uploaded screenshots
- saved places
- user feedback
- conversations
- previous trips

Weights decay over time so stale preferences fade (use a time/interaction decay,
e.g. `new = old * decay + confidence * (1 - decay)` — NOT a pure additive rule).

---

## 3. User Memory Retrieval

Before generating a plan, retrieve only the RELEVANT memories.

User: "Plan something tomorrow afternoon" → retrieve:

```
likes:    outdoor, quiet, coffee, photography
dislikes: crowded, shopping mall
```

Only relevant memories enter the planning context (not the whole profile dump).

---

## 4. Context Understanding Layer

The planner must consider:

- **Location** — e.g. San Jose
- **Time** — e.g. Saturday afternoon, 4 hours
- **Weather** — e.g. sunny, 72°F
- **Budget** — e.g. under $50
- **Transportation** — walking / driving / public transit
- **Companion** — solo / date / friends / family

---

## 5. Experience Retrieval

Do NOT recommend directly from all places. First retrieve candidates.

Sources:

- Google Places
- Event APIs
- Community trends (compliant: official APIs + user submissions, no scraping)
- User-generated experiences

Each experience should contain:

```
name, location, description, tags, vibe, best_for,
duration, cost, opening_hours, embedding
```

Example:

```
Hakone Garden
  tags:     quiet, nature, photography, date
  duration: 90 minutes
```

---

## 6. Recommendation Ranking Model

```
Final Score =
    User Preference Match
  + Current Context Match
  + Experience Quality
  + Distance
  + Weather Compatibility
  + Novelty
  - (over-)Popularity
```

Important: Do NOT rank only by popularity. A less-popular place that matches the
user should rank higher.

Matching MUST be open-vocabulary (embeddings), not a maintained keyword/tag
table — the system should understand new activities, not enumerate them.

---

## 7. Itinerary Generation Model

The AI planner behaves like a human trip designer.

Input: `User Profile + Relevant Memories + Current Context + Candidate Experiences`

Output: a structured itinerary.

```json
{
  "title": "Relaxing Japanese Style Afternoon",
  "reason": "You enjoy quiet places, photography and hidden gems.",
  "schedule": [
    {
      "time": "2:00 PM",
      "activity": "Japanese Garden",
      "duration": "90 minutes",
      "reason": "Matches your preference for nature and photography"
    },
    {
      "time": "4:00 PM",
      "activity": "Local Coffee Shop",
      "duration": "60 minutes",
      "reason": "Matches your coffee preference"
    }
  ],
  "estimated_cost": "$25",
  "transportation": "15 minute drive"
}
```

---

## 8. Planning Rules

The AI must optimize experience flow so the day feels natural.

Bad:

```
Restaurant → Museum → Park
```

Good:

```
Coffee → Walk → Sunset View → Dinner
```

---

## 9. Personalization Reasoning

Every recommendation must explain "Why this?".

Example:

```
This cafe was selected because:
  - you frequently save quiet coffee places
  - you prefer hidden gems
  - you usually avoid crowded locations
  - the weather is suitable for walking
```

---

## 10. Feedback Loop

After the activity, collect: Did you enjoy it? Was it too crowded? Would you go
again? Would you recommend it?

Update: Taste Graph → preference weights → ranking model.

---

## 11. Engineering Requirements

Implement as modular services under a `planner-service`:

- `IntentParser`
- `MemoryRetriever`
- `ExperienceRetriever`
- `RankingEngine`
- `ItineraryGenerator`
- `FeedbackProcessor`

---

## 12. Future AI Improvement

The system should support:

- reinforcement learning from feedback
- personalized ranking model
- user embedding fine-tuning
- multi-day planning

---

## Final Requirement

The AI planner should NOT answer:

> "Here are popular places nearby."

It should answer:

> "Based on who you are, what you usually enjoy, your current situation, and
> what is happening nearby, this is what I think you will genuinely enjoy today."

The product is not "AI generates a travel route" — it is an **AI Personal
Decision Engine** with a brain that understands the user. `prompt + places →
itinerary` has no moat; a memory-driven, retrieval + ranking + reasoning
pipeline does.

---

## Appendix — Current codebase mapping (as of 2026-07)

Much of this already exists in `backend/app`. REUSE these; do not rebuild.

| Prompt component | Status | Where |
|---|---|---|
| §3 Memory retrieval (relevant-only) | ✅ built | `services/user_memory.py` (`retrieve_user_memories`, 搜/广/推) |
| §1 User understanding / profile | ✅ built | `services/personalization.py` (`build_user_profile`) |
| §6 Ranking (multi-signal, not popularity-only) | ✅ built | `services/rag_pipeline.py` (`_score_doc`, fusion weights) |
| §6 Open-vocab matching (no keyword index) | ✅ built | `services/discovery.py` (pure-embedding rank) |
| §5 Experience retrieval + candidates | ✅ partial | `services/experiences.py` (OSM), `trending_store.py`, `poi_search.py` |
| §5 Experience entity (tags/vibe/duration/embedding) | ⚠️ partial | `TrendingSpot` has name/coords/tags/blurb; missing vibe/duration/cost/opening_hours/embedding |
| §4 Context (location/time/weather) | ✅ partial | planner + `services/signals.py` (weather); missing budget/companion/transit as first-class |
| §7 Itinerary generation (grounded JSON) | ✅ built | `agents/grounded.py`, `agents/planner.py` |
| §9 Personalization reasoning ("why this") | ✅ built | `discovery._reason`, `rag_pipeline._explain` |
| §10 Feedback loop | ✅ partial | `db.FeedbackEvent` + `user_memory.feedback_affinity`; missing post-activity prompts |
| §2 Taste Graph (weighted nodes + decay) | ❌ not built | implicit affinity only; needs a `taste_node` table + decay (see Personal Taste Engine PRD) |
| §5 Google Places / official Event APIs | ❌ not built | only OSM/Overpass + Ticketmaster today; add `PlaceProvider` abstraction |
| §12 pgvector / user-embedding fine-tune | ❌ not built | in-memory cosine today; migrate when scale warrants (see 架构技术选型 §2.6) |

**Compliance note:** community/social signals must come from official APIs or
user submissions — never scraping (see `docs/` product/compliance docs and the
`ENABLE_SOCIAL_SCRAPING` dev gate). Screenshot-derived data stays private to the
user; only OSM/Places-verified facts enter the shared catalog.
