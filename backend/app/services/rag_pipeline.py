from __future__ import annotations

import math
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from app.knowledge.corpus import Doc, build_corpus, context_for
from app.services.embeddings import Vector, embed_query, embed_texts
from app.services.geo import estimate_drive_hours, haversine_miles
from app.services.query_understanding import (
    TravelIntent,
    extract_intent,
    has_focus_query,
    llm_activity_phrase,
    preference_match_score,
    rewrite_query,
    specialty_intents,
)

# Semantic corpus gate (LLM-English phrase vs destination embeddings).
# Absolute floor rejects weak noise; relative margin requires a clear top hit
# so chatty rewrites (e.g. "Surfing near me please" @0.57) still count when
# Santa Cruz clearly leads the pack. Novel activities with flat ~0.40 scores
# fall through to Path B (POI).
_FOCUS_SEMANTIC_MIN = 0.55
_FOCUS_SEMANTIC_MARGIN = 0.04
_FOCUS_SEMANTIC_STRONG = 0.60

_TOKEN_RE = re.compile(r"[a-z0-9\u4e00-\u9fff]+", re.I)

# Scenery keywords mapped onto destination text / tags for soft matching.
_SCENERY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "aurora": ("aurora", "northern lights", "northern light", "auroral", "极光"),
    "whale": ("whale", "whales", "whale watching", "orca", "orcas", "观鲸", "鲸鱼"),
    "underwater": ("snorkel", "snorkeling", "scuba", "diving", "kelp", "reef", "浮潜", "潜水"),
    "waterfall": ("waterfall", "falls", "瀑布"),
    "lake": ("lake", "湖"),
    "mountain": ("mountain", "peak", "summit", "山"),
    "coast": ("coast", "beach", "ocean", "sea", "海岸", "海滩"),
    "desert": ("desert", "沙漠"),
    "canyon": ("canyon", "gorge", "峡谷"),
    "viewpoint": ("view", "viewpoint", "overlook", "观景"),
    "quiet": ("quiet", "peaceful", "secluded", "安静"),
}

_STRENUOUS_HINTS = ("strenuous", "steep", "challenging", "intense", "difficult hike")
_AURORA_MIN_LAT = 55.0


def _wants_aurora(intent: TravelIntent) -> bool:
    return "aurora" in specialty_intents(intent) or any(
        t in {"aurora", "极光", "northern"} for t in intent.focus_terms
    )


def _doc_has_aurora(doc: Doc) -> bool:
    text = doc.text.lower()
    return "aurora" in text or "northern light" in text


def _wants_focus(intent: TravelIntent) -> bool:
    """True when free-text carries content terms that should dominate UI prefs."""
    return has_focus_query(intent)


def corpus_has_semantic_focus(
    ranked: list,
    *,
    min_score: float = _FOCUS_SEMANTIC_MIN,
    margin: float = _FOCUS_SEMANTIC_MARGIN,
    strong: float = _FOCUS_SEMANTIC_STRONG,
) -> bool:
    """True when top corpus hits are semantically close to the activity phrase."""
    if not ranked:
        return False
    # Use semantic scores (not final_score order) so distance/push can't hide a hit.
    scores = sorted((r.scores.semantic_score for r in ranked[:8]), reverse=True)[:5]
    top = scores[0]
    if top < min_score:
        return False
    if top >= strong:
        return True
    floor = scores[-1]
    return (top - floor) >= margin


@dataclass
class ScoreBreakdown:
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    distance_score: float = 0.0
    personalization_score: float = 0.0  # 推 push
    explore_score: float = 0.0  # 广 explore / novelty
    search_score: float = 0.0  # 搜 relevance (sem+kw+tag+scenery+dist)
    tag_score: float = 0.0
    scenery_score: float = 0.0
    negative_penalty: float = 0.0
    rerank_score: float | None = None
    final_score: float = 0.0
    matched_query_terms: list[str] = field(default_factory=list)
    matched_tags: list[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RankedDestination:
    doc: Doc
    scores: ScoreBreakdown

    def to_candidate_dict(self, drive_time: str = "", drive_hours: float = 0.0) -> dict:
        return {
            "name": self.doc.dest_name,
            "lat": self.doc.lat,
            "lng": self.doc.lng,
            "drive_time": drive_time,
            "drive_hours": drive_hours,
            "score": round(self.scores.final_score, 3),
            "highlight": self.doc.highlight,
            "matched_query_terms": self.scores.matched_query_terms,
            "matched_tags": self.scores.matched_tags,
            "semantic_score": round(self.scores.semantic_score, 3),
            "keyword_score": round(self.scores.keyword_score, 3),
            "distance_score": round(self.scores.distance_score, 3),
            "personalization_score": round(self.scores.personalization_score, 3),
            "explore_score": round(self.scores.explore_score, 3),
            "search_score": round(self.scores.search_score, 3),
            "tag_score": round(self.scores.tag_score, 3),
            "scenery_score": round(self.scores.scenery_score, 3),
            "negative_penalty": round(self.scores.negative_penalty, 3),
            "final_score": round(self.scores.final_score, 3),
            "explanation": self.scores.explanation,
        }


@dataclass
class RAGResult:
    intent: TravelIntent
    ranked: list[RankedDestination]
    context_blocks: list[str]
    semantic: bool
    latency_ms: float
    validation: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    fusion_weights: dict[str, float] = field(default_factory=dict)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _cosine(a: Vector, b: Vector) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _explain(scores: ScoreBreakdown, doc: Doc, intent: TravelIntent) -> str:
    """Short human reason for UI + eval (no raw 搜/广/推 score dumps)."""
    bits: list[str] = []
    if intent.focus_terms and scores.semantic_score >= _FOCUS_SEMANTIC_MIN:
        focus = "/".join(intent.focus_terms[:3])
        bits.append(f"matches “{focus}”")
    if scores.matched_tags:
        bits.append("fits " + ", ".join(t.replace("-", " ") for t in scores.matched_tags[:3]))
    if scores.scenery_score > 0 and intent.scenery:
        bits.append("scenery: " + ", ".join(intent.scenery[:2]))
    if scores.personalization_score > 0.05:
        bits.append("matches your past trips")
    if scores.personalization_score < -0.05:
        bits.append("differs from past dislikes")
    if scores.explore_score >= 0.75 and abs(scores.personalization_score) > 0.01:
        bits.append("new for you")
    if scores.distance_score > 0.5 and not _wants_aurora(intent):
        bits.append("nearby")
    if not bits and doc.highlight:
        return doc.highlight
    if not bits:
        bits.append("good overall match")
    return "; ".join(bits) + "."


class RAGPipeline:
    """Full RAG pipeline: understand → rewrite → retrieve → filter → score →
    rerank → assemble context → (caller does grounded generation + validation)."""

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

    def _metadata_ok(
        self,
        doc: Doc,
        intent: TravelIntent,
        origin_lat: float,
        origin_lng: float,
        max_drive_hours: float,
        max_flight_hours: float,
        allow_flight: bool,
    ) -> bool:
        # Aurora needs high-latitude fly destinations — not mid-latitude day drives.
        if _wants_aurora(intent):
            if doc.travel_mode != "fly":
                return False
            if not (_doc_has_aurora(doc) or abs(doc.lat) >= _AURORA_MIN_LAT):
                return False
            if not allow_flight:
                return False
            miles = haversine_miles(origin_lat, origin_lng, doc.lat, doc.lng)
            flight_h = miles / 500.0 + 0.5
            return flight_h <= max_flight_hours

        if doc.travel_mode == "drive":
            miles = haversine_miles(origin_lat, origin_lng, doc.lat, doc.lng)
            return estimate_drive_hours(miles) <= max_drive_hours
        if not allow_flight:
            return False
        miles = haversine_miles(origin_lat, origin_lng, doc.lat, doc.lng)
        flight_h = miles / 500.0 + 0.5
        return flight_h <= max_flight_hours

    def _score_doc(
        self,
        doc: Doc,
        doc_tokens: set[str],
        qtok: set[str],
        qvec: Vector | None,
        doc_vec: Vector | None,
        intent: TravelIntent,
        origin_lat: float,
        origin_lng: float,
        personalization: float,
        explore: float = 0.5,
        weights: tuple[float, float, float] = (0.70, 0.15, 0.15),
    ) -> ScoreBreakdown:
        matched_terms = sorted(qtok & doc_tokens)
        kw = len(matched_terms) / (len(qtok) or 1)
        sem = _cosine(qvec, doc_vec) if qvec is not None and doc_vec is not None else 0.0

        miles = haversine_miles(origin_lat, origin_lng, doc.lat, doc.lng)
        hours = estimate_drive_hours(miles) if doc.travel_mode == "drive" else miles / 500.0 + 0.5
        dist = max(0.0, 1.0 - hours / 8.0)

        focus = _wants_focus(intent)
        matched_tags = sorted(set(doc.tags) & set(intent.preferences)) if intent.preferences else []
        # Equal-weight OR: any matched preference ≈ 1.0 (not overlap/len(prefs)).
        tag = preference_match_score(doc.tags, intent.preferences) if intent.preferences else 0.0
        if focus and intent.preferences:
            tag = 0.15 * tag  # soft hint only when free-text focus dominates

        scenery = 0.0
        text_l = doc.text.lower()
        for scene in intent.scenery:
            keys = _SCENERY_KEYWORDS.get(scene, (scene,))
            if any(k.lower() in text_l for k in keys):
                scenery += 1.0
        if intent.scenery and not focus:
            scenery /= len(intent.scenery)

        # Open-vocab focus: embedding similarity (not keyword substring).
        focus_hit = focus and sem >= _FOCUS_SEMANTIC_MIN
        if focus and focus_hit:
            scenery = max(scenery, sem)

        neg = 0.0
        if "strenuous" in intent.negative_preferences or intent.pace == "easy":
            if any(h in text_l for h in _STRENUOUS_HINTS):
                neg += 0.15
        if "crowded" in intent.negative_preferences and "popular" in text_l:
            neg += 0.05

        aurora = _wants_aurora(intent)
        if focus and not focus_hit:
            # Weak semantic match — don't let UI chips invent a "hit".
            neg += 0.45

        # 搜: relevance head (before push/explore fusion)
        if aurora:
            search = 0.30 * sem + 0.10 * kw + 0.05 * dist + 0.05 * tag + 0.40 * scenery
            if qvec is None:
                search = 0.20 * kw + 0.05 * dist + 0.10 * tag + 0.50 * scenery
        elif focus:
            # Semantic dominates for open-vocab free text.
            search = 0.55 * sem + 0.10 * kw + 0.15 * dist + 0.05 * tag + 0.10 * scenery
            if qvec is None:
                search = 0.25 * kw + 0.15 * dist + 0.05 * tag + 0.45 * scenery
        else:
            search = 0.45 * sem + 0.15 * kw + 0.15 * dist + 0.10 * tag + 0.10 * scenery
            if qvec is None:
                search = 0.35 * kw + 0.20 * dist + 0.20 * tag + 0.15 * scenery

        w_s, w_p, w_e = weights
        push = personalization
        final = w_s * search + w_p * push + w_e * explore - neg

        scores = ScoreBreakdown(
            semantic_score=sem,
            keyword_score=kw,
            distance_score=dist,
            personalization_score=push,
            explore_score=explore,
            search_score=search,
            tag_score=tag,
            scenery_score=scenery,
            negative_penalty=neg,
            final_score=final,
            matched_query_terms=matched_terms[:8],
            matched_tags=matched_tags,
        )
        scores.explanation = _explain(scores, doc, intent)
        return scores

    async def run(
        self,
        *,
        query: str,
        origin_lat: float,
        origin_lng: float,
        max_drive_hours: float = 3.0,
        max_flight_hours: float = 4.0,
        allow_flight: bool = False,
        preferences: list[str] | None = None,
        profile_text: str = "",
        personalization_fn: Callable[[str], float] | None = None,
        memory_ctx=None,
        k: int = 5,
        intent: TravelIntent | None = None,
    ) -> RAGResult:
        from app.observability import atraced, rag_latency_ms
        from app.services.user_memory import (
            explore_score_for_destination,
            fusion_weights,
            push_score_for_destination,
        )

        start = time.perf_counter()
        async with atraced(
            "rag.pipeline",
            attributes={"rag.query_len": len(query), "rag.k": k},
            latency_metric=rag_latency_ms,
            latency_labels={"operation": "pipeline"},
        ):
            # 1–2. Normalize + understand + rewrite
            intent = intent or extract_intent(query)
            if preferences:
                for p in preferences:
                    if p not in intent.preferences:
                        intent.preferences.append(p)
            if intent.max_drive_hours is not None:
                max_drive_hours = intent.max_drive_hours
            if intent.max_flight_hours is not None:
                max_flight_hours = max(max_flight_hours, intent.max_flight_hours)
                allow_flight = True
            if intent.allow_flight:
                allow_flight = True
            if _wants_aurora(intent):
                allow_flight = True
                max_flight_hours = max(max_flight_hours, intent.max_flight_hours or 7.0)

            # Open-vocab: LLM → English activity phrase, then embed (no synonym tables).
            activity_phrase = ""
            if _wants_focus(intent):
                activity_phrase = await llm_activity_phrase(query)

            rewrite_profile = profile_text
            if memory_ctx is not None and getattr(memory_ctx, "rewrite_hint", ""):
                rewrite_profile = (
                    f"{memory_ctx.rewrite_hint}. {profile_text}" if profile_text else memory_ctx.rewrite_hint
                )
            rewritten = rewrite_query(
                intent,
                profile_text=rewrite_profile,
                activity_phrase=activity_phrase,
            )

            await self._ensure_built()

            idxs = [
                i
                for i, d in enumerate(self._docs)
                if self._metadata_ok(
                    d, intent, origin_lat, origin_lng, max_drive_hours, max_flight_hours, allow_flight
                )
            ]
            qtok = _tokens(rewritten)
            # Embed the short activity phrase when present — cleaner than the full rewrite blob.
            embed_text = activity_phrase or rewritten
            qvec = await embed_query(embed_text) if self.semantic else None

            has_user = memory_ctx is not None or personalization_fn is not None
            cold = bool(
                memory_ctx is None
                or (not getattr(memory_ctx, "memories", None) and not getattr(memory_ctx, "visit_counts", None))
            )
            weights = fusion_weights(
                has_user=has_user,
                specialty=_wants_focus(intent),
                cold_start=cold,
            )
            w_map = {"search": weights[0], "push": weights[1], "explore": weights[2]}

            ranked: list[RankedDestination] = []
            for i in idxs:
                doc = self._docs[i]
                if memory_ctx is not None:
                    pers = push_score_for_destination(memory_ctx, doc.dest_name, doc.text)
                elif personalization_fn:
                    pers = personalization_fn(doc.dest_name)
                else:
                    pers = 0.0
                explore = explore_score_for_destination(memory_ctx, doc.dest_name, doc.tags)
                doc_vec = self._vecs[i] if self._vecs is not None else None
                scores = self._score_doc(
                    doc,
                    self._doc_tokens[i],
                    qtok,
                    qvec,
                    doc_vec,
                    intent,
                    origin_lat,
                    origin_lng,
                    pers,
                    explore=explore,
                    weights=weights,
                )
                ranked.append(RankedDestination(doc=doc, scores=scores))

            ranked.sort(key=lambda r: r.scores.final_score, reverse=True)

            if _wants_focus(intent) and not _wants_aurora(intent):
                focus_hits = [
                    r for r in ranked if r.scores.semantic_score >= _FOCUS_SEMANTIC_MIN
                ]
                if focus_hits:
                    ranked = focus_hits + [
                        r
                        for r in ranked
                        if r.scores.semantic_score < _FOCUS_SEMANTIC_MIN
                    ]

            from app.config import settings
            from app.services.rerank import rerank, rerank_available

            pool_n = max(k, settings.rerank_candidates) if settings.rerank_enabled else k
            pool = ranked[:pool_n]
            if settings.rerank_enabled and rerank_available() and len(pool) > 1:
                pairs = [(r.doc, r.scores.final_score) for r in pool]
                reranked_pairs = await rerank(rewritten, pairs, k=len(pool))
                by_name = {r.doc.dest_name: r for r in pool}
                new_ranked: list[RankedDestination] = []
                for doc, rscore in reranked_pairs:
                    item = by_name[doc.dest_name]
                    item.scores.rerank_score = rscore
                    item.scores.final_score = 0.6 * rscore + 0.4 * item.scores.final_score
                    item.scores.explanation = _explain(item.scores, doc, intent)
                    new_ranked.append(item)
                new_ranked.sort(key=lambda r: r.scores.final_score, reverse=True)
                ranked = new_ranked + [r for r in ranked if r.doc.dest_name not in by_name]
            else:
                ranked = ranked[:k] + ranked[k:]

            top = ranked[:k]

            context_blocks = [
                f"[{i+1}] {r.doc.dest_name}: {context_for(r.doc.dest_name) or r.doc.text}"
                for i, r in enumerate(top[:3])
            ]
            if memory_ctx is not None and getattr(memory_ctx, "memory_blocks", None):
                context_blocks.extend(memory_ctx.memory_blocks[:3])
            elif profile_text and "none yet" not in profile_text.lower():
                context_blocks.append(f"[profile] {profile_text}")

            validation = {
                "has_results": len(top) > 0,
                "constraint_drive_ok": all(
                    self._metadata_ok(
                        r.doc,
                        intent,
                        origin_lat,
                        origin_lng,
                        max_drive_hours,
                        max_flight_hours,
                        allow_flight,
                    )
                    for r in top
                ),
                "scenery_coverage": (
                    sum(1 for r in top if r.scores.scenery_score > 0) / len(top) if top else 0.0
                ),
                "top_has_explanation": bool(top and top[0].scores.explanation),
                "memory_hits": len(getattr(memory_ctx, "retrieved", []) or []),
            }

            ms = (time.perf_counter() - start) * 1000
            return RAGResult(
                intent=intent,
                ranked=top,
                context_blocks=context_blocks,
                semantic=self.semantic,
                latency_ms=round(ms, 2),
                validation=validation,
                memory=memory_ctx.to_dict() if memory_ctx is not None and hasattr(memory_ctx, "to_dict") else {},
                fusion_weights=w_map,
            )


# Module singleton (index built once).
rag_pipeline = RAGPipeline()


# Back-compat thin wrapper used by chat refiner.
class Retriever:
    async def retrieve(
        self,
        query: str,
        k: int = 5,
        predicate: Callable[[Doc], bool] | None = None,
    ) -> list[tuple[Doc, float]]:
        await rag_pipeline._ensure_built()
        result = await rag_pipeline.run(
            query=query,
            origin_lat=37.77,
            origin_lng=-122.42,
            max_drive_hours=12.0,
            max_flight_hours=12.0,
            allow_flight=True,
            k=k,
        )
        out = [(r.doc, r.scores.final_score) for r in result.ranked]
        if predicate:
            out = [(d, s) for d, s in out if predicate(d)]
        return out[:k]

    @property
    def semantic(self) -> bool:
        return rag_pipeline.semantic


retriever = Retriever()
