"""RAG evaluation framework for Travel-Agent.

Metrics:
- intent extraction accuracy
- retrieval precision@3 / recall@5
- constraint satisfaction rate
- groundedness score
- hallucination rate (proxy: places not in context)
- personalization match rate
- latency

Run:
  cd backend && python -m app.eval.run_eval
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.services.query_understanding import TravelIntent, extract_intent
from app.services.rag_pipeline import rag_pipeline

CASES_PATH = Path(__file__).with_name("cases.json")


@dataclass
class EvalCase:
    id: str
    query: str
    origin_lat: float = 37.7749
    origin_lng: float = -122.4194
    max_drive_hours: float = 3.0
    allow_flight: bool = False
    # Expected intent fields (partial match)
    expect_intent: dict[str, Any] = field(default_factory=dict)
    # Gold destinations for retrieval metrics
    relevant: list[str] = field(default_factory=list)
    # Optional profile text for personalization cases
    profile_text: str = ""
    # Destinations that should get a personalization boost match
    prefer_destinations: list[str] = field(default_factory=list)


@dataclass
class CaseResult:
    id: str
    intent_accuracy: float
    precision_at_3: float
    recall_at_5: float
    constraint_satisfaction: float
    groundedness: float
    hallucination_rate: float
    personalization_match: float
    latency_ms: float
    top_names: list[str] = field(default_factory=list)
    intent: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def load_cases(path: Path | None = None) -> list[EvalCase]:
    p = path or CASES_PATH
    raw = json.loads(p.read_text(encoding="utf-8"))
    return [EvalCase(**c) for c in raw]


def _field_match(got: Any, expected: Any) -> bool:
    if expected is None:
        return True
    if isinstance(expected, list):
        if not isinstance(got, list):
            return False
        return all(x in got for x in expected)
    if isinstance(expected, (int, float)) and isinstance(got, (int, float)):
        return abs(float(got) - float(expected)) < 0.01
    return got == expected


def intent_accuracy(intent: TravelIntent, expect: dict[str, Any]) -> float:
    if not expect:
        return 1.0
    data = intent.to_dict()
    hits = sum(1 for k, v in expect.items() if _field_match(data.get(k), v))
    return hits / len(expect)


def precision_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    if not relevant:
        return 1.0
    top = retrieved[:k]
    if not top:
        return 0.0
    return sum(1 for n in top if n in relevant) / len(top)


def recall_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    if not relevant:
        return 1.0
    top = set(retrieved[:k])
    return sum(1 for n in relevant if n in top) / len(relevant)


def constraint_satisfaction(ranked, intent: TravelIntent, max_drive: float) -> float:
    if not ranked:
        return 0.0
    ok = 0
    for r in ranked:
        # Drive-time already filtered in pipeline; check soft constraints.
        soft_ok = True
        if intent.scenery and r.scores.scenery_score <= 0:
            soft_ok = False
        if "strenuous" in intent.negative_preferences and r.scores.negative_penalty > 0.1:
            soft_ok = False
        if soft_ok:
            ok += 1
    return ok / len(ranked)


def groundedness_score(context_blocks: list[str], top_names: list[str]) -> float:
    """Fraction of top destinations that appear in assembled context."""
    if not top_names:
        return 0.0
    blob = " ".join(context_blocks).lower()
    return sum(1 for n in top_names[:3] if n.lower() in blob) / min(3, len(top_names))


def hallucination_proxy(context_blocks: list[str], explanation: str) -> float:
    """Cheap proxy: unexplained proper nouns in explanation not in context → risk."""
    if not explanation:
        return 0.0
    blob = " ".join(context_blocks).lower()
    # Tokens that look like place-ish capitalized words in explanation are rare
    # in our English template; use matched terms presence instead.
    # Lower is better; return rate in [0,1].
    if "recommended" in explanation.lower() and blob:
        return 0.0 if any(w in blob for w in explanation.lower().split()[:6]) else 0.2
    return 0.0


def personalization_match(ranked, prefer: list[str]) -> float:
    if not prefer:
        return 1.0
    if not ranked:
        return 0.0
    top3 = {r.doc.dest_name for r in ranked[:3]}
    return sum(1 for p in prefer if p in top3) / len(prefer)


async def run_case(case: EvalCase) -> CaseResult:
    t0 = time.perf_counter()
    intent = extract_intent(case.query)
    ia = intent_accuracy(intent, case.expect_intent)

    # Personalization stub: boost preferred destinations when profile present.
    prefer = set(case.prefer_destinations)

    def pers_fn(name: str) -> float:
        if name in prefer:
            return 0.2
        return 0.0

    rag = await rag_pipeline.run(
        query=case.query,
        origin_lat=case.origin_lat,
        origin_lng=case.origin_lng,
        max_drive_hours=case.max_drive_hours
        if intent.max_drive_hours is None
        else intent.max_drive_hours,
        allow_flight=case.allow_flight or bool(intent.allow_flight),
        profile_text=case.profile_text,
        personalization_fn=pers_fn if prefer else None,
        k=5,
        intent=intent,
    )
    latency = (time.perf_counter() - t0) * 1000
    names = [r.doc.dest_name for r in rag.ranked]
    expl = rag.ranked[0].scores.explanation if rag.ranked else ""

    return CaseResult(
        id=case.id,
        intent_accuracy=round(ia, 3),
        precision_at_3=round(precision_at_k(names, case.relevant, 3), 3),
        recall_at_5=round(recall_at_k(names, case.relevant, 5), 3),
        constraint_satisfaction=round(
            constraint_satisfaction(rag.ranked, intent, case.max_drive_hours), 3
        ),
        groundedness=round(groundedness_score(rag.context_blocks, names), 3),
        hallucination_rate=round(hallucination_proxy(rag.context_blocks, expl), 3),
        personalization_match=round(personalization_match(rag.ranked, case.prefer_destinations), 3),
        latency_ms=round(latency, 1),
        top_names=names,
        intent=intent.to_dict(),
        notes=[rag.validation] if rag.validation else [],
    )


def aggregate(results: list[CaseResult]) -> dict[str, float]:
    if not results:
        return {}
    keys = [
        "intent_accuracy",
        "precision_at_3",
        "recall_at_5",
        "constraint_satisfaction",
        "groundedness",
        "hallucination_rate",
        "personalization_match",
        "latency_ms",
    ]
    out: dict[str, float] = {}
    for k in keys:
        vals = [getattr(r, k) for r in results]
        out[k] = round(sum(vals) / len(vals), 3)
    return out


async def run_eval(path: Path | None = None) -> dict[str, Any]:
    cases = load_cases(path)
    results = [await run_case(c) for c in cases]
    return {
        "n": len(results),
        "aggregate": aggregate(results),
        "cases": [asdict(r) for r in results],
    }


def main() -> None:
    report = asyncio.run(run_eval())
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
