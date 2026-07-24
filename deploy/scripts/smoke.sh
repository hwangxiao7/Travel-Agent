#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PORT="${HTTP_PORT:-8080}"
BASE="http://127.0.0.1:${PORT}"

cd "$ROOT"

if ! docker compose -f deploy/docker-compose.yml ps --status running 2>/dev/null | grep -q travel-agent; then
  echo "Stack not running. Start with:"
  echo "  docker compose -f deploy/docker-compose.yml up -d --build"
  exit 1
fi

echo "Smoke: ${BASE}/api/health"
curl -fsS "${BASE}/api/health" | head -c 200
echo

echo "Smoke: ${BASE}/ (SPA index)"
curl -fsS -o /dev/null -w "HTTP %{http_code}\n" "${BASE}/"

echo "OK"
