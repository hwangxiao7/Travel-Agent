# Suggested Commands

## Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# configure .env at repo root (see .env.example)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Frontend
```bash
cd frontend && npm install && npm run dev   # http://127.0.0.1:5173
```

## RAG evaluation
```bash
cd backend && python -m app.eval.run_eval
```

## Local LLM (Ollama) — optional, in root .env
```env
LLM_PROVIDER=openai
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
OPENAI_MODEL=qwen2.5:3b
OPENAI_EMBED_MODEL=nomic-embed-text
```

## Optional local PyTorch RAG
```env
EMBEDDING_BACKEND=local
RERANK_ENABLED=true
```

## Notes
- All API keys are optional; SQLite default: `backend/data/travel.db`.
- Demo path: start backend :8000 → iOS Local or Web :5173 → run Surprise/Planner → sign in → double-tap like → submit feedback (triggers low-score email alert).
- Do NOT hardcode internal company gateways; keep OpenAI-compatible so Ollama/hosted can be swapped. Repo must not contain internal tokens.
