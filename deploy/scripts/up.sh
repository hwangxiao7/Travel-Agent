#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy deploy/env.example to .env and edit secrets."
  exit 1
fi

docker compose -f deploy/docker-compose.yml up -d --build "$@"

echo "Web: http://127.0.0.1:${HTTP_PORT:-8080}"
echo "Run ./deploy/scripts/smoke.sh to verify."
