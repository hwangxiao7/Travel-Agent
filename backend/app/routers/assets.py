"""Lightweight asset serving — no request-time image generation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.asset_vibes import VIBE_KEYS, all_activity_vibe_map
from app.services.assets import list_known_keys, resolve_asset_path, sync_assets_from_disk

router = APIRouter(prefix="/api/assets", tags=["assets"])


@router.get("/manifest")
def asset_manifest(db: Session = Depends(get_db)):
    sync_assets_from_disk(db)
    return {
        "vibes": list(VIBE_KEYS),
        "activity_vibe": all_activity_vibe_map(),
        "keys": list_known_keys(),
        "cache_hint": {"max_bytes": 20 * 1024 * 1024, "max_files": 100},
    }


@router.get("/{key}")
def get_asset(key: str, db: Session = Depends(get_db)):
    # Normalize: allow "vibe-adventure" or "vibe_adventure"
    key = key.strip().replace("_", "-")
    if not key or "/" in key or ".." in key:
        raise HTTPException(status_code=400, detail="Invalid asset key")
    resolved = resolve_asset_path(key, db)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    path, mime = resolved
    return FileResponse(
        path,
        media_type=mime,
        headers={
            "Cache-Control": "public, max-age=604800",
            "X-Asset-Key": key,
        },
    )
