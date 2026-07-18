# Spontaneous Travel Agent — FastAPI backend
# Target: local smoke + AWS EC2. Secrets via --env-file .env (not baked in).
#
# Build (repo root):
#   docker build -t travel-agent-api .
#
# Run (SQLite in named volume):
#   docker run -d --name travel-agent -p 8000:8000 \
#     --env-file .env \
#     -v travel-agent-data:/app/backend/data \
#     travel-agent-api
#
# Health: GET http://<host>:8000/api/health
#
# Runtime env (see .env.example):
#   LLM_PROVIDER / OPENAI_*     — text LLM + embeddings
#   INSPIRATION_EXTRACT_MODE    — auto | ocr_text | vision (screenshot 种草)
#   OPENAI_VISION_MODEL         — optional VL fallback when mode=auto|vision
#   JWT_SECRET / CORS_ORIGINS   — production hardening

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Screenshot inspiration: local OCR first, vision LLM only on fallback
    INSPIRATION_EXTRACT_MODE=auto

WORKDIR /app

# System packages (keep slim — only what Python wheels need at runtime)
#   curl           — HEALTHCHECK probe
#   libgomp1       — onnxruntime (rapidocr-onnxruntime)
#   libglib2.0-0   — opencv / image decode (Pillow + rapidocr)
#   libgl1         — headless OpenCV on Debian slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libgomp1 \
        libglib2.0-0 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

# Python deps — see backend/requirements.txt
#   Core API: fastapi, uvicorn, sqlalchemy, auth, multipart upload
#   LLM: openai, anthropic
#   Observability: opentelemetry, prometheus
#   Screenshot OCR: rapidocr-onnxruntime, Pillow, numpy (+ onnxruntime, opencv via pip)
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
RUN mkdir -p /app/backend/data \
    && chown -R appuser:appuser /app

USER appuser
WORKDIR /app/backend

EXPOSE 8000

# First OCR request may load ONNX models (~20s); allow warm startup
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
