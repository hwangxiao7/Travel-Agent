"""On-disk media assets with SQLite catalog — serve by key, keep the app light.

Layout:
  backend/app/knowledge/assets/<key>.webp   (canonical bytes)
  MediaAsset row                            (key, mime, size, version)

Clients: try bundled → local LRU disk cache → GET /api/assets/{key}.
We never generate images at request time.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import MediaAsset
from app.services.asset_vibes import CORE_ICON_KEYS, VIBE_KEYS

_ASSETS_DIR = Path(__file__).resolve().parents[1] / "knowledge" / "assets"


def assets_dir() -> Path:
    _ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    return _ASSETS_DIR


def sync_assets_from_disk(db: Session) -> int:
    """Upsert MediaAsset rows for every file under knowledge/assets/."""
    root = assets_dir()
    n = 0
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue
        key = path.stem  # vibe-adventure.webp → vibe-adventure
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        size = path.stat().st_size
        row = db.scalar(select(MediaAsset).where(MediaAsset.key == key))
        if row is None:
            db.add(
                MediaAsset(
                    key=key,
                    kind="vibe" if key.startswith("vibe-") else "core",
                    filename=path.name,
                    mime=mime,
                    byte_size=size,
                    version=1,
                )
            )
            n += 1
        else:
            row.filename = path.name
            row.mime = mime
            row.byte_size = size
            n += 1
    db.commit()
    return n


def resolve_asset_path(key: str, db: Session | None = None) -> tuple[Path, str] | None:
    """Return (path, mime) for a key, preferring DB metadata when present."""
    root = assets_dir()
    if db is not None:
        row = db.scalar(select(MediaAsset).where(MediaAsset.key == key))
        if row is not None:
            path = root / row.filename
            if path.is_file():
                return path, row.mime
    for ext in (".webp", ".png", ".jpg", ".jpeg"):
        path = root / f"{key}{ext}"
        if path.is_file():
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            return path, mime
    return None


def list_known_keys() -> list[str]:
    return list(CORE_ICON_KEYS) + list(VIBE_KEYS)
