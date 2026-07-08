from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.config import settings

# On-disk cache so the (static) corpus is embedded once, not on every startup.
_CACHE_PATH = Path(__file__).resolve().parents[1] / "knowledge" / ".embed_cache.json"

Vector = list[float]


def _embeddings_available() -> bool:
    # Needs a key AND an embedding model. Leave openai_embed_model empty to
    # disable semantic retrieval (e.g. on endpoints without an embedding model).
    return bool(settings.openai_api_key and settings.openai_embed_model)


def _cache_key(text: str) -> str:
    raw = f"{settings.openai_embed_model}\n{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_cache() -> dict[str, Vector]:
    try:
        return json.loads(_CACHE_PATH.read_text("utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict[str, Vector]) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(cache), "utf-8")
    except Exception:
        pass


async def _openai_embed(texts: list[str]) -> list[Vector] | None:
    from openai import AsyncOpenAI

    client_kwargs = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    client = AsyncOpenAI(**client_kwargs)
    try:
        resp = await client.embeddings.create(model=settings.openai_embed_model, input=texts)
        return [d.embedding for d in resp.data]
    except Exception:
        return None


async def embed_texts(texts: list[str]) -> list[Vector] | None:
    """Embed a batch, using the disk cache for already-seen strings.

    Returns None when embeddings are unavailable (no key) so callers can fall
    back to keyword retrieval."""
    if not texts or not _embeddings_available():
        return None

    cache = _load_cache()
    missing = [t for t in texts if _cache_key(t) not in cache]
    if missing:
        fresh = await _openai_embed(missing)
        if fresh is None:
            return None
        for text, vec in zip(missing, fresh):
            cache[_cache_key(text)] = vec
        _save_cache(cache)

    return [cache[_cache_key(t)] for t in texts]


async def embed_query(text: str) -> Vector | None:
    result = await embed_texts([text])
    return result[0] if result else None
