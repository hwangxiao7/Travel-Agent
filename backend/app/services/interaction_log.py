"""Funnel event logging for the collective-intelligence layer (P1).

Captures "想做什么 → 选了什么 → 去了哪 → 反馈如何" as `InteractionEvent` rows,
tagged with the user's persona snapshot at event time so the nightly rollup
(`app.services.crowd`) can aggregate cross-user affinity per personality bucket.

Privacy: events are only written for logged-in users who have NOT opted out
(`User.crowd_opt_out`). Every call is best-effort — logging must never break or
slow down the actual request, so all failures are swallowed.
"""

from __future__ import annotations


# --- intent keys (coarse, aggregatable) -------------------------------------

def intent_for_activities(energy: str = "", companion: str = "") -> str:
    e = (energy or "any").strip().lower()
    c = (companion or "any").strip().lower()
    return f"act:{e}|{c}"


def intent_for_plan(preferences, trip_type: str = "") -> str:
    prefs = sorted({str(p).strip().lower() for p in (preferences or []) if str(p).strip()})
    tag = (trip_type or "trip").strip().lower()
    return f"plan:{tag}:{','.join(prefs) or 'any'}"


# --- persona snapshot -------------------------------------------------------

def _snapshot(persona) -> str:
    """Serialize persona axis scores + confidence as 's0,s1,...;conf'."""
    from app.services.persona import AXES

    try:
        scores = getattr(persona, "scores", {}) or {}
        vals = ",".join(f"{float(scores.get(a, 50.0)):.0f}" for a in AXES)
        return f"{vals};{float(getattr(persona, 'confidence', 0.0)):.2f}"
    except Exception:
        return ""


def snapshot_scores(snapshot: str) -> tuple[dict[str, float], float]:
    """Parse a stored snapshot back into (scores, confidence). Empty → neutral."""
    from app.services.persona import AXES

    try:
        body, _, conf = snapshot.partition(";")
        parts = [float(x) for x in body.split(",")] if body else []
        scores = {a: (parts[i] if i < len(parts) else 50.0) for i, a in enumerate(AXES)}
        return scores, (float(conf) if conf else 0.0)
    except Exception:
        return {a: 50.0 for a in AXES}, 0.0


# --- write path -------------------------------------------------------------

def log_events(user, events: list[dict], *, persona=None) -> None:
    """Persist a batch of funnel events for `user` (best-effort, own session).

    `events` items: {stage, surface, item_key, item_name, item_kind,
                     intent_key?, outcome_value?}. `item_key` is normalized here.
    """
    if user is None or not events:
        return
    if getattr(user, "crowd_opt_out", False):
        return
    try:
        from app.db import InteractionEvent, SessionLocal, get_engine, place_key
        from app.services.persona import get_or_build_persona

        get_engine()
        if SessionLocal is None:
            return
        db = SessionLocal()
        try:
            if persona is None:
                persona = get_or_build_persona(db, user)
            snap = _snapshot(persona)
            for e in events:
                name = (e.get("item_name") or "").strip()
                db.add(
                    InteractionEvent(
                        user_id=user.id,
                        stage=e["stage"],
                        surface=e.get("surface", ""),
                        intent_key=(e.get("intent_key") or "")[:120],
                        item_key=(e.get("item_key") or (place_key(name) if name else ""))[:220],
                        item_name=name[:200],
                        item_kind=e.get("item_kind", ""),
                        outcome_value=float(e.get("outcome_value", 0.0) or 0.0),
                        persona_snapshot=snap,
                    )
                )
            db.commit()
        finally:
            db.close()
    except Exception:
        # Never let telemetry break the request.
        return


def log_event(user, **event) -> None:
    log_events(user, [event])
