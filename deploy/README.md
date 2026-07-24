# Web + API deployment stack

Single-machine layout for **China Web beta** (and US later with the same compose file):

```
Browser ──► nginx (web) ──► static React build
              │
              └── /api/* ──► FastAPI (api) ──► SQLite volume
```

WeChat login uses the **existing website OAuth** flow (`/api/auth/wechat/*`). It requires **HTTPS + registered redirect URI** — use HTTP on `:8080` for email/login smoke tests until your domain is ready.

## Quick start (no domain yet)

```bash
# From repo root (Travel-Agent/)
cp deploy/env.example .env
# Edit .env: at minimum OPENAI_API_KEY + JWT_SECRET

docker compose -f deploy/docker-compose.yml up -d --build
./deploy/scripts/smoke.sh
```

Open **http://127.0.0.1:8080** — Surprise me / Trip planner call same-origin `/api/*`.

Stop:

```bash
docker compose -f deploy/docker-compose.yml down
```

Data persists in Docker volume `travel-agent-data`.

## When you have a domain

| Step | Action |
|------|--------|
| 1 | Point DNS A record → cloud VM public IP |
| 2 | ICP 备案 (China) |
| 3 | TLS cert (e.g. certbot) → `deploy/certs/fullchain.pem` + `privkey.pem` |
| 4 | Copy `deploy/nginx/ssl.conf.example` → `deploy/nginx/ssl.conf`, set `YOUR_DOMAIN` |
| 5 | Mount TLS config in `docker-compose.yml` (see comment in `ssl.conf.example`) |
| 6 | Update `.env`: `CORS_ORIGINS=https://YOUR_DOMAIN`, `AUTH_WECHAT_ENABLED=true`, `WECHAT_*` |
| 7 | WeChat 开放平台 → 网站应用 → redirect URI exactly `https://YOUR_DOMAIN/api/auth/wechat/callback` |

## Files

| File | Role |
|------|------|
| `docker-compose.yml` | `api` + `web` services |
| `Dockerfile.web` | Build frontend, nginx image |
| `nginx/default.conf` | HTTP reverse proxy (dev / pre-TLS) |
| `nginx/ssl.conf.example` | HTTPS template |
| `env.example` | Minimal production `.env` starter |

## Notes

- API is **not** published on a host port; only nginx `:8080` (or `:443` later) is public.
- `/metrics` is blocked on the web port; scrape from inside the Docker network if needed.
- iOS / second region: same API image; point clients at region-specific domains later.
