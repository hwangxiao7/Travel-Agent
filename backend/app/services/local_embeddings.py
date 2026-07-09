from __future__ import annotations

import asyncio
from typing import Any

from app.config import settings

# Process-level singleton — loading a SentenceTransformer is expensive.
_model: Any | None = None
_load_error: str | None = None


def _pick_device() -> str:
    try:
        import torch

        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _get_model() -> Any | None:
    """Lazy-load the local embedding model once per process."""
    global _model, _load_error
    if _model is not None:
        return _model
    if _load_error is not None:
        return None
    try:
        from sentence_transformers import SentenceTransformer

        device = _pick_device()
        _model = SentenceTransformer(settings.local_embed_model, device=device)
        return _model
    except Exception as exc:
        _load_error = str(exc)
        return None


def local_embeddings_available() -> bool:
    return _get_model() is not None


def _encode_sync(texts: list[str]) -> list[list[float]] | None:
    model = _get_model()
    if model is None:
        return None
    # normalize_embeddings=True → cosine via dot product is well-behaved
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    return [v.tolist() for v in vectors]


async def embed_texts_local(texts: list[str]) -> list[list[float]] | None:
    """Embed via local PyTorch / sentence-transformers (runs in a worker thread)."""
    if not texts:
        return []
    return await asyncio.to_thread(_encode_sync, texts)
