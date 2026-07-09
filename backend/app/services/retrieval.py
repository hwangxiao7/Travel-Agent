from __future__ import annotations

import math
import re
from typing import Callable

from app.knowledge.corpus import Doc, build_corpus
from app.services.embeddings import Vector, embed_query, embed_texts

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _cosine(a: Vector, b: Vector) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class Retriever:
    """Lazy, in-memory hybrid retriever over the destination corpus.

    Uses semantic (embedding) similarity when a key is configured, and always
    blends in a lightweight keyword-overlap score. Falls back to keyword-only
    when embeddings are unavailable, so search works with zero external keys."""

    def __init__(self) -> None:
        self._docs: list[Doc] = []
        self._vecs: list[Vector] | None = None
        self._doc_tokens: list[set[str]] = []
        self._built = False

    async def _ensure_built(self) -> None:
        if self._built:
            return
        self._docs = build_corpus()
        self._doc_tokens = [_tokens(d.text) for d in self._docs]
        self._vecs = await embed_texts([d.text for d in self._docs])
        self._built = True

    @property
    def semantic(self) -> bool:
        return self._vecs is not None

    async def retrieve(
        self,
        query: str,
        k: int = 5,
        predicate: Callable[[Doc], bool] | None = None,
    ) -> list[tuple[Doc, float]]:
        from app.observability import atraced, rag_latency_ms

        async with atraced(
            "retrieval.search",
            attributes={"rag.query_len": len(query), "rag.k": k},
            latency_metric=rag_latency_ms,
            latency_labels={"operation": "search"},
        ):
            await self._ensure_built()

            idxs = [i for i, d in enumerate(self._docs) if predicate is None or predicate(d)]
            if not idxs:
                return []

            qtok = _tokens(query)
            qvec = await embed_query(query) if self.semantic else None

            scored: list[tuple[Doc, float]] = []
            for i in idxs:
                doc = self._docs[i]
                kw = len(qtok & self._doc_tokens[i]) / (len(qtok) or 1)
                if qvec is not None and self._vecs is not None:
                    sem = _cosine(qvec, self._vecs[i])
                    score = 0.75 * sem + 0.25 * kw
                else:
                    score = kw
                scored.append((doc, score))

            scored.sort(key=lambda x: x[1], reverse=True)

            # Optional cross-encoder rerank over a wider candidate pool.
            from app.config import settings
            from app.services.rerank import rerank

            pool = max(k, settings.rerank_candidates) if settings.rerank_enabled else k
            top = scored[:pool]
            if settings.rerank_enabled and len(top) > 1:
                return await rerank(query, top, k)
            return top[:k]


# Module-level singleton (index built once, on first query).
retriever = Retriever()
