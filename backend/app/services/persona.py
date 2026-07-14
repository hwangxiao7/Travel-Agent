"""Travel persona: abstract MBTI-style taste axes for a user.

Instead of a flat list of checkboxes, a user is summarized on six bipolar axes
(0–100, 50 neutral). Scores are derived from behavior (feedback events, reviews,
trips) and an optional onboarding quiz, then a fun type code + title + blurb are
generated from the dominant axes. The axes also bias ranking so recommendations
match the user's character.

Axes (score 0 = first pole, 100 = second pole):
  indoor_outdoor    Indoor(I)      ↔ Outdoor(O)
  calm_adventurous  Calm(C)        ↔ Adventurous(A)
  culture_nature    Culture(U)     ↔ Nature(N)
  quiet_social      Quiet(Q)       ↔ Social(S)
  leisurely_active  Leisurely(L)   ↔ Active(T)
  popular_novel     Popular(P)     ↔ Novel/Hidden(X)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import FeedbackEvent, PlaceReview, TravelPersona, Trip, User

AXES = [
    "indoor_outdoor",
    "calm_adventurous",
    "culture_nature",
    "quiet_social",
    "leisurely_active",
    "popular_novel",
]

# (low-pole label, high-pole label, low letter, high letter, low adj, high adj, low noun, high noun)
_AXIS_META: dict[str, dict] = {
    "indoor_outdoor": {"low": "Indoor", "high": "Outdoor", "lc": "I", "hc": "O",
                        "ladj": "Cozy", "hadj": "Outdoorsy", "lnoun": "Homebody", "hnoun": "Explorer"},
    "calm_adventurous": {"low": "Calm", "high": "Adventurous", "lc": "C", "hc": "A",
                          "ladj": "Easygoing", "hadj": "Daring", "lnoun": "Relaxer", "hnoun": "Adventurer"},
    "culture_nature": {"low": "Culture", "high": "Nature", "lc": "U", "hc": "N",
                        "ladj": "Cultured", "hadj": "Wild", "lnoun": "Culture Seeker", "hnoun": "Nature Lover"},
    "quiet_social": {"low": "Quiet", "high": "Social", "lc": "Q", "hc": "S",
                      "ladj": "Solitary", "hadj": "Sociable", "lnoun": "Solitude Seeker", "hnoun": "Social Butterfly"},
    "leisurely_active": {"low": "Leisurely", "high": "Active", "lc": "L", "hc": "T",
                          "ladj": "Slow-paced", "hadj": "Energetic", "lnoun": "Slow Traveler", "hnoun": "Go-Getter"},
    "popular_novel": {"low": "Popular", "high": "Novel", "lc": "P", "hc": "X",
                       "ladj": "Classic", "hadj": "Curious", "lnoun": "Icon Collector", "hnoun": "Hidden-Gem Hunter"},
}

# Keyword → per-axis nudge in [-1, 1] (toward high pole positive). Scanned against
# a destination's name + corpus text. Open-ended but small & interpretable.
_KEYWORD_AXES: list[tuple[tuple[str, ...], dict[str, float]]] = [
    (("national park", "national-park"), {"indoor_outdoor": 1.0, "culture_nature": 0.9, "leisurely_active": 0.4}),
    (("hiking", "hike", "trail", "徒步"), {"indoor_outdoor": 1.0, "culture_nature": 0.7, "leisurely_active": 1.0, "calm_adventurous": 0.6}),
    (("forest", "redwood", "woods", "森林"), {"indoor_outdoor": 0.8, "culture_nature": 1.0, "quiet_social": -0.4}),
    (("beach", "surf", "coast", "海"), {"indoor_outdoor": 0.8, "leisurely_active": 0.3, "calm_adventurous": 0.4}),
    (("surf", "kayak", "climb", "dive", "snorkel", "冲浪", "攀岩"), {"calm_adventurous": 1.0, "leisurely_active": 1.0, "indoor_outdoor": 1.0}),
    (("city", "urban", "downtown", "city-walk", "城市"), {"indoor_outdoor": -0.2, "culture_nature": -0.7, "quiet_social": 0.5}),
    (("museum", "gallery", "art", "history", "博物馆", "美术"), {"indoor_outdoor": -0.8, "culture_nature": -1.0, "quiet_social": -0.2}),
    (("food", "cafe", "coffee", "restaurant", "美食", "咖啡"), {"quiet_social": 0.4, "culture_nature": -0.3}),
    (("whale", "aurora", "northern light", "观鲸", "极光"), {"popular_novel": 0.7, "calm_adventurous": 0.5, "culture_nature": 0.6}),
    (("escape room", "paintball", "axe", "arcade", "密室", "真人cs"), {"quiet_social": 0.8, "leisurely_active": 0.7, "popular_novel": 0.6, "indoor_outdoor": -0.3}),
    (("hidden", "secret", "off the beaten", "local", "小众"), {"popular_novel": 0.9}),
    (("iconic", "famous", "must-see", "landmark", "popular"), {"popular_novel": -0.8}),
    (("quiet", "peaceful", "secluded", "安静"), {"quiet_social": -0.7, "calm_adventurous": -0.4}),
]

_LIKE_EVENTS = {"save": 1.0, "visit": 0.9, "share": 0.7, "click": 0.25}


@dataclass
class Persona:
    scores: dict[str, float] = field(default_factory=lambda: {a: 50.0 for a in AXES})
    confidence: float = 0.0
    type_code: str = ""
    title: str = "Balanced Traveler"
    blurb: str = ""
    quiz: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "scores": {a: round(self.scores.get(a, 50.0), 1) for a in AXES},
            "axes": [
                {
                    "key": a,
                    "low": _AXIS_META[a]["low"],
                    "high": _AXIS_META[a]["high"],
                    "score": round(self.scores.get(a, 50.0), 1),
                }
                for a in AXES
            ],
            "confidence": round(self.confidence, 2),
            "type_code": self.type_code,
            "title": self.title,
            "blurb": self.blurb,
            "has_quiz": bool(self.quiz),
        }


def _resolve_text(destination: str) -> str:
    """Destination name + curated corpus text (if catalogued) for keyword scan."""
    from app.knowledge.corpus import context_for

    return f"{destination} {context_for(destination)}".lower()


def _nudge_from_text(text: str, weight: float, acc: dict[str, float], counts: dict[str, float]) -> None:
    for keys, axes in _KEYWORD_AXES:
        if any(k in text for k in keys):
            for axis, v in axes.items():
                acc[axis] = acc.get(axis, 0.0) + v * weight
                counts[axis] = counts.get(axis, 0.0) + abs(weight)


def _quiz_scores(quiz: dict) -> dict[str, float]:
    """Map quiz answers (axis → -1..1 lean) to 0-100 anchors."""
    out: dict[str, float] = {}
    for axis, lean in (quiz or {}).items():
        if axis in AXES:
            try:
                out[axis] = max(0.0, min(100.0, 50.0 + float(lean) * 45.0))
            except (TypeError, ValueError):
                continue
    return out


def compute_persona(db: Session, user: User, *, quiz_weight: float = 0.45) -> Persona:
    """Derive persona from behavior + reviews + trips, blended with quiz answers.

    quiz_weight: fraction of quiz vs behavior when both exist (0..1).
    Explicit quiz retakes pass a higher weight so answers actually move the persona.
    """
    quiz_weight = max(0.0, min(1.0, quiz_weight))
    behavior_weight = 1.0 - quiz_weight
    acc: dict[str, float] = {}
    counts: dict[str, float] = {}
    n_signals = 0

    # Feedback events → like/dislike weighted nudges.
    for e in db.scalars(select(FeedbackEvent).where(FeedbackEvent.user_id == user.id)).all():
        dest = (e.destination or e.place_name or "").strip()
        if not dest:
            continue
        if e.event_type == "rate":
            w = 0.4 * (float(e.value or 3.0) - 3.0)  # -0.8..+0.8
        elif e.event_type == "skip":
            w = -0.6
        else:
            w = _LIKE_EVENTS.get(e.event_type, 0.0)
        if abs(w) < 0.01:
            continue
        _nudge_from_text(_resolve_text(dest), w, acc, counts)
        n_signals += 1

    # Reviews → rating-weighted nudges.
    for r in db.scalars(select(PlaceReview).where(PlaceReview.user_id == user.id)).all():
        w = 0.5 * (float(r.rating) - 3.0)
        if abs(w) < 0.01:
            continue
        _nudge_from_text(f"{r.place_name} {r.destination}".lower(), w, acc, counts)
        n_signals += 1

    # Trips → mild positive nudges (visited = leans toward that character).
    for t in db.scalars(select(Trip).where(Trip.user_id == user.id)).all():
        _nudge_from_text(_resolve_text(t.destination), 0.4, acc, counts)
        n_signals += 1

    # Behavior-derived axis scores (0-100).
    behavior_scores: dict[str, float] = {}
    for axis in AXES:
        c = counts.get(axis, 0.0)
        if c > 0:
            avg = acc[axis] / c  # -1..1
            behavior_scores[axis] = max(0.0, min(100.0, 50.0 + avg * 45.0))

    # Quiz anchors.
    stored = db.scalar(select(TravelPersona).where(TravelPersona.user_id == user.id))
    quiz = {}
    if stored and stored.quiz_json:
        try:
            quiz = json.loads(stored.quiz_json)
        except json.JSONDecodeError:
            quiz = {}
    quiz_scores = _quiz_scores(quiz)

    # Blend quiz (stable prior) with behavior (adapts over time).
    scores: dict[str, float] = {}
    for axis in AXES:
        b = behavior_scores.get(axis)
        q = quiz_scores.get(axis)
        if b is not None and q is not None:
            scores[axis] = quiz_weight * q + behavior_weight * b
        elif b is not None:
            scores[axis] = b
        elif q is not None:
            scores[axis] = q
        else:
            scores[axis] = 50.0

    confidence = min(1.0, n_signals * 0.1 + (0.55 if quiz_scores else 0.0))
    p = Persona(scores=scores, confidence=confidence, quiz=quiz)
    _label(p)
    return p


def prefs_from_persona(p: Persona) -> list[str]:
    """Map persona axes → Preference chip values for trip planner / discovery."""
    s = p.scores
    prefs: list[str] = []
    if s.get("indoor_outdoor", 50) >= 58:
        prefs.extend(["hiking", "forest"])
    if s.get("culture_nature", 50) >= 58:
        prefs.extend(["national-park", "forest"])
    elif s.get("culture_nature", 50) <= 42:
        prefs.append("city-walk")
    if s.get("leisurely_active", 50) >= 58:
        prefs.append("hiking")
    if s.get("indoor_outdoor", 50) >= 55 and s.get("calm_adventurous", 50) >= 52:
        prefs.append("beach")
    if s.get("culture_nature", 50) <= 45 and s.get("quiet_social", 50) >= 55:
        prefs.append("city-walk")
    # Dedupe, keep order, cap.
    return list(dict.fromkeys(prefs))[:4]


def apply_quiz_to_user(db: Session, user: User, persona: Persona) -> None:
    """After quiz: write taste snippets + default preference chips (so RAG/plan learn)."""
    from app.services.taste_profile import record_snippet

    prefs = prefs_from_persona(persona)
    if prefs:
        user.default_prefs = json.dumps(prefs)
        db.commit()
        db.refresh(user)

    # Open-vocab taste so /api/activities + /api/discover personalize.
    bits = [
        f"Travel persona: {persona.title}. {persona.blurb}".strip(),
        "Prefers: " + ", ".join(prefs) if prefs else "",
    ]
    for axis in AXES:
        score = persona.scores.get(axis, 50.0)
        if abs(score - 50) < 12:
            continue
        m = _AXIS_META[axis]
        pole = m["high"] if score >= 50 else m["low"]
        bits.append(f"Leans {pole.lower()} ({axis.replace('_', ' ')})")
    text = " ".join(b for b in bits if b)
    if text:
        record_snippet(db, user, text, source="quiz", weight=1.2, polarity=1.0)


def quiz_questions(language: str = "en") -> list[dict]:
    """Return quiz questions; zh gets translated copy, same ids/leans."""
    zh = (language or "en").lower().startswith("zh")
    if not zh:
        return QUIZ
    out: list[dict] = []
    for q in QUIZ:
        t = _QUIZ_ZH.get(q["id"])
        if not t:
            out.append(q)
            continue
        opts = []
        for o in q["options"]:
            label = t["options"].get(o["id"], o["label"])
            opts.append({**o, "label": label})
        out.append({**q, "q": t["q"], "options": opts})
    return out


# Chinese copy for QUIZ (ids must match).
_QUIZ_ZH: dict[str, dict] = {
    "afternoon": {
        "q": "有一个空闲的下午，你更想…",
        "options": {
            "trail": "去户外走走、徒步",
            "cafe": "逛博物馆或咖啡馆",
            "friends": "和朋友去热闹的地方",
            "home": "在家安静充电",
        },
    },
    "energy": {
        "q": "理想的外出感觉是…",
        "options": {
            "thrill": "有点刺激、动起来",
            "balanced": "动静平衡",
            "calm": "轻松、休息",
        },
    },
    "company": {
        "q": "你最喜欢怎样探索…",
        "options": {
            "group": "一群人，热闹场所",
            "partner": "和一个人，轻松随意",
            "solo": "独自，安静角落",
        },
    },
    "backdrop": {
        "q": "选一个让你开心的场景：",
        "options": {
            "mountains": "山与森林",
            "coast": "海边沙滩",
            "city": "城市街道与美食",
        },
    },
    "discover": {
        "q": "你更想去…",
        "options": {
            "hidden": "本地小众宝藏",
            "iconic": "必打卡的知名景点",
        },
    },
    "mornings": {
        "q": "周末早上，你更可能…",
        "options": {
            "workout": "出门徒步或运动",
            "brunch": "早午餐 + 慢悠悠散步",
            "sleepin": "睡懒觉",
        },
    },
    "whim": {
        "q": "一时兴起，你会答应…",
        "options": {
            "surf": "冲浪或攀岩体验课",
            "newfood": "一家新的小馆子",
            "exhibit": "快闪艺术展",
            "drive": "开着车随便兜风",
        },
    },
    "crowds": {
        "q": "对于人多热闹的场面…",
        "options": {
            "love": "喜欢那种热闹",
            "avoid": "更爱安静的地方",
        },
    },
    "water": {
        "q": "在水边，你会…",
        "options": {
            "inwater": "下水——游泳、冲浪、皮划艇",
            "beside": "坐在旁边放松",
            "meh": "不太喜欢水相关",
        },
    },
    "planning": {
        "q": "去一个新地方时，你会…",
        "options": {
            "wing": "随缘，走到哪算哪",
            "loose": "有个大概想法",
            "plan": "把细节都安排好",
        },
    },
    "evening": {
        "q": "理想的夜晚是…",
        "options": {
            "livemusic": "现场音乐或酒吧",
            "dinner": "一顿安静的晚餐",
            "stargaze": "找个安静地方看星星",
        },
    },
    "naturedose": {
        "q": "你最爱的自然剂量：",
        "options": {
            "summit": "登顶看大风景",
            "forest": "安静的森林散步",
            "park": "漂亮的城市公园",
        },
    },
}


def _label(p: Persona) -> None:
    """Generate type code + title + blurb from the axis scores."""
    code = ""
    for axis in AXES:
        m = _AXIS_META[axis]
        code += m["hc"] if p.scores[axis] >= 50 else m["lc"]
    p.type_code = code

    # Rank axes by how far they lean from neutral.
    ranked = sorted(AXES, key=lambda a: abs(p.scores[a] - 50), reverse=True)
    strongest, second = ranked[0], ranked[1]
    if abs(p.scores[strongest] - 50) < 8 or p.confidence < 0.15:
        p.title = "Balanced Traveler"
        p.blurb = "Still learning your style — explore a few trips and your persona will sharpen."
        return

    def side(axis: str, key_low: str, key_high: str) -> str:
        m = _AXIS_META[axis]
        return m[key_high] if p.scores[axis] >= 50 else m[key_low]

    noun = side(strongest, "lnoun", "hnoun")
    adj = side(second, "ladj", "hadj")
    p.title = f"{adj} {noun}"
    hi = side(strongest, "low", "high").lower()
    hi2 = side(second, "low", "high").lower()
    p.blurb = f"You lean {hi} and {hi2} — expect picks that feel {adj.lower()} and {noun.lower()} in spirit."


def persona_from_row(row: TravelPersona) -> Persona:
    scores = {a: float(getattr(row, a, 50.0)) for a in AXES}
    quiz = {}
    if row.quiz_json:
        try:
            quiz = json.loads(row.quiz_json)
        except json.JSONDecodeError:
            quiz = {}
    p = Persona(scores=scores, confidence=float(row.confidence or 0.0), quiz=quiz)
    _label(p)
    return p


def save_persona(db: Session, user: User, p: Persona) -> TravelPersona:
    from datetime import datetime

    row = db.scalar(select(TravelPersona).where(TravelPersona.user_id == user.id))
    if row is None:
        row = TravelPersona(user_id=user.id)
        db.add(row)
    for axis in AXES:
        setattr(row, axis, p.scores.get(axis, 50.0))
    row.confidence = p.confidence
    row.quiz_json = json.dumps(p.quiz or {})
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def set_manual_scores(db: Session, user: User, scores: dict) -> Persona:
    """User drags the axis sliders → override scores, persist, relabel.

    Manual edits raise confidence (the user is telling us directly) and stick
    until they retake the quiz. Feeds `persona_bias`, so ranking adapts.
    """
    p = get_or_build_persona(db, user)
    for axis, val in (scores or {}).items():
        if axis in AXES:
            try:
                p.scores[axis] = max(0.0, min(100.0, float(val)))
            except (TypeError, ValueError):
                continue
    p.confidence = max(p.confidence, 0.5)
    _label(p)
    save_persona(db, user, p)
    return p


def get_or_build_persona(db: Session, user: User, *, recompute: bool = False) -> Persona:
    """Return stored persona, or compute + persist one from behavior."""
    row = db.scalar(select(TravelPersona).where(TravelPersona.user_id == user.id))
    if row is not None and not recompute:
        return persona_from_row(row)
    p = compute_persona(db, user)
    save_persona(db, user, p)
    return p


def persona_bias(persona: Persona | None, *, tags, text: str) -> float:
    """Ranking nudge in ~[-0.12, 0.12]: how well a candidate matches the persona.

    Scaled by confidence so a fresh user isn't over-personalized.
    """
    if persona is None or persona.confidence < 0.1:
        return 0.0
    acc: dict[str, float] = {}
    counts: dict[str, float] = {}
    blob = (str(text) + " " + " ".join(tags or [])).lower()
    _nudge_from_text(blob, 1.0, acc, counts)
    if not counts:
        return 0.0
    total = 0.0
    n = 0
    for axis, c in counts.items():
        if c <= 0:
            continue
        cand_lean = acc[axis] / c  # -1..1 (toward high pole)
        user_lean = (persona.scores[axis] - 50) / 50.0  # -1..1
        total += cand_lean * user_lean
        n += 1
    if n == 0:
        return 0.0
    return max(-0.12, min(0.12, (total / n) * 0.12 * persona.confidence))


# --- Onboarding quiz (each option leans one or more axes by -1..1) ---

# ~12 quick questions. Each option nudges one or more axes (-1..1). Coverage is
# intentionally redundant (every axis touched by 3+ questions) so the base
# persona is robust from the quiz alone. Options can be 2–4 per question.
QUIZ = [
    {
        "id": "afternoon",
        "q": "A free afternoon opens up. You'd rather…",
        "options": [
            {"id": "trail", "label": "Get outside on a trail", "lean": {"indoor_outdoor": 1, "leisurely_active": 0.6, "culture_nature": 0.6}},
            {"id": "cafe", "label": "Wander a museum or café", "lean": {"indoor_outdoor": -1, "culture_nature": -0.9}},
            {"id": "friends", "label": "Meet up with friends somewhere lively", "lean": {"quiet_social": 1, "indoor_outdoor": -0.2}},
            {"id": "home", "label": "Recharge quietly at home", "lean": {"indoor_outdoor": -0.8, "quiet_social": -0.8, "leisurely_active": -0.8}},
        ],
    },
    {
        "id": "energy",
        "q": "Your ideal outing feels…",
        "options": [
            {"id": "thrill", "label": "Adventurous and active", "lean": {"calm_adventurous": 1, "leisurely_active": 0.9}},
            {"id": "balanced", "label": "A bit of both", "lean": {"calm_adventurous": 0.1, "leisurely_active": 0.1}},
            {"id": "calm", "label": "Calm and restful", "lean": {"calm_adventurous": -1, "leisurely_active": -0.9}},
        ],
    },
    {
        "id": "company",
        "q": "You most enjoy exploring…",
        "options": [
            {"id": "group", "label": "With a group, buzzing places", "lean": {"quiet_social": 1}},
            {"id": "partner", "label": "With one person, easygoing", "lean": {"quiet_social": -0.1, "calm_adventurous": -0.2}},
            {"id": "solo", "label": "Solo, quiet corners", "lean": {"quiet_social": -1}},
        ],
    },
    {
        "id": "backdrop",
        "q": "Pick your happy place:",
        "options": [
            {"id": "mountains", "label": "Mountains & forests", "lean": {"culture_nature": 1, "indoor_outdoor": 0.8}},
            {"id": "coast", "label": "Ocean & beaches", "lean": {"culture_nature": 0.6, "indoor_outdoor": 0.7}},
            {"id": "city", "label": "City streets & food", "lean": {"culture_nature": -1, "indoor_outdoor": -0.4, "quiet_social": 0.4}},
        ],
    },
    {
        "id": "discover",
        "q": "You'd rather visit…",
        "options": [
            {"id": "hidden", "label": "A hidden local gem", "lean": {"popular_novel": 1}},
            {"id": "iconic", "label": "The iconic must-see", "lean": {"popular_novel": -1}},
        ],
    },
    {
        "id": "mornings",
        "q": "Weekend mornings, you're most likely…",
        "options": [
            {"id": "workout", "label": "Out for a hike or workout", "lean": {"leisurely_active": 1, "indoor_outdoor": 0.6, "calm_adventurous": 0.4}},
            {"id": "brunch", "label": "Brunch and a slow stroll", "lean": {"leisurely_active": -0.5, "culture_nature": -0.4}},
            {"id": "sleepin", "label": "Sleeping in", "lean": {"leisurely_active": -1}},
        ],
    },
    {
        "id": "whim",
        "q": "On a whim, you'd say yes to…",
        "options": [
            {"id": "surf", "label": "A surf or climbing lesson", "lean": {"calm_adventurous": 1, "leisurely_active": 0.8, "indoor_outdoor": 0.8, "popular_novel": 0.4}},
            {"id": "newfood", "label": "A new hole-in-the-wall restaurant", "lean": {"popular_novel": 0.7, "culture_nature": -0.5, "quiet_social": 0.3}},
            {"id": "exhibit", "label": "A pop-up art exhibit", "lean": {"culture_nature": -0.9, "indoor_outdoor": -0.7, "popular_novel": 0.5}},
            {"id": "drive", "label": "A scenic drive to nowhere", "lean": {"calm_adventurous": -0.3, "culture_nature": 0.5, "indoor_outdoor": 0.4}},
        ],
    },
    {
        "id": "crowds",
        "q": "Crowds and busy scenes…",
        "options": [
            {"id": "love", "label": "Love the buzz", "lean": {"quiet_social": 1, "popular_novel": -0.4}},
            {"id": "avoid", "label": "Prefer quiet spots", "lean": {"quiet_social": -1, "popular_novel": 0.5}},
        ],
    },
    {
        "id": "water",
        "q": "By the water, you're…",
        "options": [
            {"id": "inwater", "label": "In it — swim, surf, kayak", "lean": {"calm_adventurous": 0.9, "leisurely_active": 0.9, "indoor_outdoor": 0.8}},
            {"id": "beside", "label": "Beside it, relaxing", "lean": {"leisurely_active": -0.6, "calm_adventurous": -0.5, "indoor_outdoor": 0.4}},
            {"id": "meh", "label": "Not really a water person", "lean": {"indoor_outdoor": -0.5}},
        ],
    },
    {
        "id": "planning",
        "q": "When you go somewhere new, you…",
        "options": [
            {"id": "wing", "label": "Wing it and see what happens", "lean": {"calm_adventurous": 0.7, "popular_novel": 0.7}},
            {"id": "loose", "label": "Have a loose idea", "lean": {"popular_novel": 0.1}},
            {"id": "plan", "label": "Plan the details", "lean": {"calm_adventurous": -0.5, "popular_novel": -0.5}},
        ],
    },
    {
        "id": "evening",
        "q": "A great evening out is…",
        "options": [
            {"id": "livemusic", "label": "Live music or a bar", "lean": {"quiet_social": 1, "indoor_outdoor": -0.3}},
            {"id": "dinner", "label": "A cozy dinner", "lean": {"quiet_social": -0.2, "culture_nature": -0.4}},
            {"id": "stargaze", "label": "Stargazing somewhere quiet", "lean": {"quiet_social": -0.8, "culture_nature": 0.8, "indoor_outdoor": 0.8}},
        ],
    },
    {
        "id": "naturedose",
        "q": "Your favorite dose of nature:",
        "options": [
            {"id": "summit", "label": "A summit with big views", "lean": {"culture_nature": 1, "leisurely_active": 0.9, "calm_adventurous": 0.8, "indoor_outdoor": 0.9}},
            {"id": "forest", "label": "A quiet forest walk", "lean": {"culture_nature": 0.9, "quiet_social": -0.5, "indoor_outdoor": 0.7}},
            {"id": "park", "label": "A pretty city park", "lean": {"culture_nature": -0.3, "leisurely_active": -0.4, "indoor_outdoor": 0.2}},
        ],
    },
]


def quiz_answers_to_leans(answers: dict[str, str]) -> dict[str, float]:
    """Map {question_id: option_id} → {axis: averaged lean -1..1}."""
    acc: dict[str, list[float]] = {}
    for q in QUIZ:
        chosen = answers.get(q["id"])
        opt = next((o for o in q["options"] if o["id"] == chosen), None)
        if not opt:
            continue
        for axis, lean in opt["lean"].items():
            acc.setdefault(axis, []).append(float(lean))
    return {axis: sum(v) / len(v) for axis, v in acc.items() if v}
