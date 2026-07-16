"""Collective-intelligence aggregation (P2): cross-user affinity per persona bucket.

Nightly rollup over `InteractionEvent` → `CrowdSignal`, keyed by persona bucket ×
item at several backoff granularities. Serving enforces k-anonymity (only buckets
covering >= K distinct users are returned), so no single user's behavior leaks.

Run the rollup:  python -m app.services.crowd
Wire into ranking later (P3) via `crowd_affinity()` / `top_items_for_persona()`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import CrowdSignal, InteractionEvent
from app.services.interaction_log import snapshot_scores
from app.services.persona import persona_bucket_keys

# Only serve an aggregate once it covers at least this many distinct users.
K_ANONYMITY = 3
# Events older than this are ignored so the crowd tracks current tastes.
_LOOKBACK_DAYS = 180


def _affinity(n_shown: int, n_selected: int, n_saved: int, n_rated: int, rating_sum: float) -> float:
    """Blend engagement (save/select vs shown) with rating quality → 0..1."""
    denom = max(n_shown, n_saved + n_selected, 1)
    engagement = (1.0 * n_saved + 0.4 * n_selected) / denom
    engagement = min(1.0, engagement)
    if n_rated > 0:
        avg = rating_sum / n_rated  # 1..5
        quality = max(0.0, min(1.0, (avg - 3.0) / 2.0))
    else:
        quality = 0.5  # neutral when unrated
    return round(min(1.0, 0.6 * engagement + 0.4 * quality), 4)


def rebuild_crowd_signals(db: Session, *, lookback_days: int = _LOOKBACK_DAYS) -> dict:
    """Recompute all crowd signals from the event log. Full rebuild (idempotent)."""
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)
    events = db.scalars(
        select(InteractionEvent).where(InteractionEvent.created_at >= cutoff)
    ).all()

    # (bucket_key, item_key) -> accumulator
    agg: dict[tuple[str, str], dict] = {}
    for e in events:
        if not e.item_key:
            continue
        scores, _conf = snapshot_scores(e.persona_snapshot)
        for bkey in persona_bucket_keys(scores):
            acc = agg.setdefault(
                (bkey, e.item_key),
                {
                    "name": e.item_name,
                    "kind": e.item_kind,
                    "users": set(),
                    "shown": 0,
                    "selected": 0,
                    "saved": 0,
                    "rated": 0,
                    "rating_sum": 0.0,
                },
            )
            acc["users"].add(e.user_id)
            if e.item_name and not acc["name"]:
                acc["name"] = e.item_name
            if e.stage == "shown":
                acc["shown"] += 1
            elif e.stage == "selected":
                acc["selected"] += 1
            elif e.stage == "saved":
                acc["saved"] += 1
            elif e.stage == "rated":
                acc["rated"] += 1
                acc["rating_sum"] += float(e.outcome_value or 0.0)

    db.execute(delete(CrowdSignal))
    now = datetime.utcnow()
    n_rows = 0
    for (bkey, item_key), acc in agg.items():
        db.add(
            CrowdSignal(
                bucket_key=bkey,
                item_key=item_key,
                item_name=acc["name"] or "",
                item_kind=acc["kind"] or "",
                n_users=len(acc["users"]),
                n_shown=acc["shown"],
                n_selected=acc["selected"],
                n_saved=acc["saved"],
                n_rated=acc["rated"],
                rating_sum=acc["rating_sum"],
                affinity=_affinity(
                    acc["shown"], acc["selected"], acc["saved"], acc["rated"], acc["rating_sum"]
                ),
                updated_at=now,
            )
        )
        n_rows += 1
    db.commit()
    return {"events": len(events), "rows": n_rows, "buckets": len({k for k, _ in agg})}


# --- serving (used by P3 ranking; safe to call now) -------------------------

def crowd_affinity(
    db: Session, persona, item_keys: list[str], *, k: int = K_ANONYMITY
) -> dict[str, float]:
    """Return {item_key: affinity 0..1} for the given items, using the most
    specific persona bucket that meets the k-anonymity threshold. Items with no
    qualifying aggregate are omitted (caller treats as neutral)."""
    if persona is None or not item_keys:
        return {}
    scores = getattr(persona, "scores", None) or {}
    out: dict[str, float] = {}
    remaining = set(item_keys)
    for bkey in persona_bucket_keys(scores):  # specific → general
        if not remaining:
            break
        rows = db.scalars(
            select(CrowdSignal).where(
                CrowdSignal.bucket_key == bkey,
                CrowdSignal.item_key.in_(list(remaining)),
                CrowdSignal.n_users >= k,
            )
        ).all()
        for r in rows:
            out[r.item_key] = r.affinity
            remaining.discard(r.item_key)
    return out


def top_items_for_persona(
    db: Session, persona, *, kind: str | None = None, limit: int = 8, k: int = K_ANONYMITY
) -> list[dict]:
    """'People like you loved…' — top items in the user's most specific bucket
    that meets k-anonymity. Returns [{item_key, item_name, item_kind, affinity, n_users}]."""
    if persona is None:
        return []
    scores = getattr(persona, "scores", None) or {}
    for bkey in persona_bucket_keys(scores):
        q = select(CrowdSignal).where(
            CrowdSignal.bucket_key == bkey, CrowdSignal.n_users >= k
        )
        if kind:
            q = q.where(CrowdSignal.item_kind == kind)
        rows = db.scalars(q.order_by(CrowdSignal.affinity.desc()).limit(limit)).all()
        if rows:
            return [
                {
                    "item_key": r.item_key,
                    "item_name": r.item_name,
                    "item_kind": r.item_kind,
                    "affinity": r.affinity,
                    "n_users": r.n_users,
                }
                for r in rows
            ]
    return []


if __name__ == "__main__":
    from app.db import SessionLocal, get_engine, init_db

    init_db()
    get_engine()
    assert SessionLocal is not None
    _db = SessionLocal()
    try:
        summary = rebuild_crowd_signals(_db)
        print("crowd rollup:", summary)
    finally:
        _db.close()
