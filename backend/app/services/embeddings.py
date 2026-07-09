from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.config import settings

# On-disk cache so the (static) corpus is embedded once, not on every startup.
_CACHE_PATH = Path(__file__).resolve().parents[1] / "knowledge" / ".embed_cache.json"

Vector = list[float]


def _embed_model_id() -> str:
    if settings.embedding_backend.lower() == "local":
        return f"local:{settings.local_embed_model}"
    return f"api:{settings.openai_embed_model}"


def _embeddings_available() -> bool:
    if settings.embedding_backend.lower() == "local":
        from app.services.local_embeddings import local_embeddings_available

        return local_embeddings_available()
    # API path: needs a key AND an embedding model.
    return bool(settings.openai_api_key and settings.openai_embed_model)


def _cache_key(text: str) -> str:
    raw = f"{_embed_model_id()}\n{text}".encode("utf-8")
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


async def _embed_fresh(texts: list[str]) -> list[Vector] | None:
    if settings.embedding_backend.lower() == "local":
        from app.services.local_embeddings import embed_texts_local

        return await embed_texts_local(texts)
    return await _openai_embed(texts)


async def embed_texts(texts: list[str]) -> list[Vector] | None:
    """Embed a batch, using the disk cache for already-seen strings.

    Returns None when embeddings are unavailable so callers can fall back to
    keyword retrieval. Backend is selected by EMBEDDING_BACKEND=api|local."""
    from app.observability import (
        atraced,
        rag_latency_ms,
        record_cache_hit,
        record_cache_miss,
        record_external_failure,
    )

    if not texts or not _embeddings_available():
        return None

    async with atraced(
        "embeddings.embed",
        attributes={
            "embed.count": len(texts),
            "embed.backend": settings.embedding_backend,
            "embed.model": _embed_model_id(),
        },
        latency_metric=rag_latency_ms,
        latency_labels={"operation": "embed"},
    ):
        cache = _load_cache()
        missing = [t for t in texts if _cache_key(t) not in cache]
        hits = len(texts) - len(missing)
        record_cache_hit(hits)
        record_cache_miss(len(missing))
        if missing:
            fresh = await _embed_fresh(missing)
            if fresh is None:
                record_external_failure("embeddings")
                return None
            for text, vec in zip(missing, fresh):
                cache[_cache_key(text)] = vec
            _save_cache(cache)

        return [cache[_cache_key(t)] for t in texts]


async def embed_query(text: str) -> Vector | None:
    result = await embed_texts([text])
    return result[0] if result else None
