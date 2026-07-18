---
name: dockerfile-deps-audit
description: >-
  Audits whether backend changes need Dockerfile, requirements.txt, .env.example,
  or HEALTHCHECK updates for the Travel-Agent API image. Use when adding Python
  packages, native/OCR/ML libraries, multipart uploads, new runtime env vars,
  slow cold-start features, or when the user mentions Docker, EC2, container
  deploy, docker build, or "写进 Dockerfile".
---

# Dockerfile dependency audit (Travel-Agent)

This repo ships the **FastAPI backend only** via root `Dockerfile`. iOS/Web are **not** in the image.

## When to run this audit

Run **before finishing** any backend change that touches:

- `backend/requirements.txt` or new `import` of a native-heavy library
- Image/audio/video processing, OCR, ONNX, PyTorch, OpenCV, cryptography backends
- New `settings` fields in `backend/app/config.py` that affect runtime behavior
- Features with slow first request (model load, large index build)
- New upload endpoints (`multipart`, file size limits)

Skip for: pure business logic, iOS/Web-only, docs-only (unless Docker docs).

## Two-layer install model

| Layer | File | What goes here |
|-------|------|----------------|
| Python wheels | `backend/requirements.txt` | All `pip install` packages |
| OS runtime libs | `Dockerfile` `apt-get` | What wheels **cannot** bundle (`.so`, fonts, CLI probes) |

**Rule:** new pip dep → add to `requirements.txt` **and** check if Dockerfile needs apt packages.

## Audit checklist

Copy and complete:

```
Dockerfile audit:
- [ ] requirements.txt updated (if new pip dep)
- [ ] Dockerfile apt-get updated (if native .so needed)
- [ ] Dockerfile ENV default (if new config with sensible container default)
- [ ] .env.example documented (secrets / deploy knobs — never bake secrets in image)
- [ ] HEALTHCHECK start-period (if cold start >20s)
- [ ] .dockerignore still excludes .env, backend/data/, ios/, frontend/node_modules/
- [ ] README Docker section still accurate (one paragraph max)
- [ ] docs/CHANGELOG.md entry (if substantive backend/deploy change)
```

## Decision tree: pip only vs apt too?

1. **Pure Python** (httpx, pydantic, sqlalchemy) → `requirements.txt` only.
2. **Wheel includes binaries** but needs system libs (common case):
   - `onnxruntime`, `rapidocr-onnxruntime` → `libgomp1`
   - `opencv-python` / OCR / Pillow-heavy paths → `libglib2.0-0`, often `libgl1` on `python:*-slim`
   - `cryptography` / `python-jose` → usually fine on slim; if build fails, add `gcc` only in build stage (avoid in final image if possible)
3. **PyTorch / sentence-transformers** (`EMBEDDING_BACKEND=local`) → large; keep **commented optional** in requirements unless product requires it; Dockerfile may need `libgomp1`, multi-GB image — call out in CHANGELOG.
4. **CLI used in HEALTHCHECK or CMD** → apt install that CLI (`curl` for `/api/health`).

Full pip→apt hints: [package-apt-map.md](package-apt-map.md).

## This repo's Dockerfile conventions

Path: **`/Dockerfile`** (repo root, not `backend/`).

```dockerfile
# Pattern — keep comments listing WHY each apt package exists
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \          # HEALTHCHECK
        libgomp1 \      # onnxruntime
        libglib2.0-0 \  # opencv / glib
        libgl1 \        # headless opencv on Debian slim
    && rm -rf /var/lib/apt/lists/*
```

- Base: `python:3.12-slim`
- Install order: apt → `COPY requirements.txt` → `pip install` → `COPY backend/`
- Run as non-root `appuser` (uid 10001)
- Secrets: **`--env-file .env` at run time** — never `COPY .env`
- Data: volume mount `/app/backend/data` for SQLite
- Default env in image only for **non-secret safe defaults** (e.g. `INSPIRATION_EXTRACT_MODE=auto`)

## Config / env sync

When adding `Settings` fields:

| Kind | Dockerfile | .env.example |
|------|------------|--------------|
| Secret (API keys, JWT) | ❌ never | ✅ documented, empty default |
| Safe default for containers | ✅ `ENV` optional | ✅ commented example |
| Local-only dev | ❌ | ✅ |

## HEALTHCHECK

Current: `curl -fsS http://127.0.0.1:8000/api/health`

Increase `--start-period` when a feature loads heavy assets on first use (OCR ONNX ~20s → use 45s+).

## Verify (when Docker available)

```bash
docker build -t travel-agent-api .
docker run --rm -p 8000:8000 --env-file .env travel-agent-api
curl -fsS http://127.0.0.1:8000/api/health
```

If Docker unavailable, still update files and note "build not verified locally".

## Anti-patterns

- ❌ `pip install` only in README, not in `requirements.txt`
- ❌ Native lib works on Mac dev but missing apt on slim → production crash on import
- ❌ Baking `.env` or JWT secrets into image
- ❌ Copying `ios/` or `frontend/node_modules/` (`.dockerignore` prevents this)
- ❌ Duplicating the same dep in Dockerfile pip **and** requirements with different versions

## Example triggers (this project)

| Change | Action |
|--------|--------|
| Added `rapidocr-onnxruntime` | requirements + `libgomp1` `libglib2.0-0` `libgl1` + HEALTHCHECK 45s |
| Added `INSPIRATION_EXTRACT_MODE` | `config.py` + `.env.example` + optional `ENV` in Dockerfile |
| Added `torch` for local embed | optional requirements comment; warn image size; `libgomp1` |
| New `POST` multipart upload | `python-multipart` in requirements (already present) |
