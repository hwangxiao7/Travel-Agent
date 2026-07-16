# Lightweight sticker / activity icons

**Date:** 2026-07-15  
**Choice:** Vibe-group icons (option A) — ~10 stickers cover the whole activity catalog.

## Layers

| Tier | What | Where |
|---|---|---|
| L0 bundled | Core chrome (mascot, prefs, trip types) + vibe set | iOS `Icons/` (~176KB), Web `/icons/*.webp` (~172KB) |
| L1 device LRU | Rare/future remote keys | iOS Caches/`sticker-assets` (20MB / 100 files) |
| L2 server | Canonical files + `media_assets` rows | `backend/app/knowledge/assets/*.webp`, `GET /api/assets/{key}` |

Never generate images on the request path. Never ship one PNG per activity.

## Mapping

`activity_key` → `icon_key` via `asset_vibes.vibe_for_activity` (returned on `/api/activities` as `icon_key`).

## Clients

- iOS `AssetStore` + `StickerImage(allowRemote:)`
- Web `AssetImg` (local webp → `/api/assets/{key}` on error)
