# Spontaneous Travel Agent — FastAPI backend
# Target: local smoke + AWS EC2 (docker run / compose). Secrets via env, not baked in.
#
# Build (from repo root):
#   docker build -t travel-agent-api .
#
# Run (SQLite persists in a named volume):
#   docker run -d --name travel-agent -p 8000:8000 \
#     --env-file .env \
#     -v travel-agent-data:/app/backend/data \
#     travel-agent-api
#
# Health: GET http://<host>:8000/api/health

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
RUN mkdir -p /app/backend/data \
    && chown -R appuser:appuser /app

USER appuser
WORKDIR /app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
