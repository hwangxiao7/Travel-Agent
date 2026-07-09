from __future__ import annotations

import asyncio
from typing import Any

from app.config import settings
from app.knowledge.corpus import Doc

# Process-level singleton for the cross-encoder.
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
    global _model, _load_error
    if _model is not None:
        return _model
    if _load_error is not None:
        return None
    try:
        from sentence_transformers import CrossEncoder

        _model = CrossEncoder(settings.rerank_model, device=_pick_device())
        return _model
    except Exception as exc:
        _load_error = str(exc)
        return None


def rerank_available() -> bool:
    return settings.rerank_enabled and _get_model() is not None


def _rerank_sync(query: str, docs: list[Doc]) -> list[float]:
    model = _get_model()
    if model is None:
        return [0.0] * len(docs)
    pairs = [(query, d.text) for d in docs]
    scores = model.predict(pairs, show_progress_bar=False)
    return [float(s) for s in scores]


async def rerank(
    query: str, scored: list[tuple[Doc, float]], k: int
) -> list[tuple[Doc, float]]:
    """Re-score hybrid candidates with a cross-encoder; return top-k.

    Best-effort: if the model isn't available, returns the original list truncated."""
    if not scored or not settings.rerank_enabled:
        return scored[:k]

    from app.observability import atraced, rag_latency_ms

    async with atraced(
        "retrieval.rerank",
        attributes={"rerank.candidates": len(scored), "rerank.k": k},
        latency_metric=rag_latency_ms,
        latency_labels={"operation": "rerank"},
    ):
        if not rerank_available():
            return scored[:k]
        docs = [d for d, _ in scored]
        scores = await asyncio.to_thread(_rerank_sync, query, docs)
        reranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return list(reranked[:k])
