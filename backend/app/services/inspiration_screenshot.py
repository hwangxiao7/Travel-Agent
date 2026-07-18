"""User-submitted screenshot inspiration — private Taste RAG path.

Compliance boundary (no scraping, no shared catalog by default):
- The user voluntarily uploads their own screenshot.
- We process the image in memory and discard it — only structured facts +
  taste snippets are persisted, scoped to that user.
- We never write to TrendingSpot / shared corpus from this path.
- Extracted text is rewritten into neutral planning facts (our words), not a
  stored copy of the post caption.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db import User, UserInspirationCapture
from app.models.schemas import InspirationCaptureOut, InspirationPlaceOut
from app.services.geocode import geocode as geocode_query
from app.services.llm import analyze_image_json
from app.services.taste_profile import invalidate, record_snippet

_MAX_BYTES = 4 * 1024 * 1024
_ALLOWED_MIME = frozenset({"image/jpeg", "image/png", "image/webp"})

_EXTRACT_SYSTEM = (
    "You read travel inspiration screenshots (social posts, notes, itineraries). "
    "Extract planning facts in YOUR OWN WORDS — do not copy long captions verbatim.\n"
    "Return ONLY JSON with this shape:\n"
    '{"activity_title":"short name","summary":"one neutral sentence",'
    '"places":[{"name_en":"English/geocodable name","name_local":"original if any"}],'
    '"suggested_times":["e.g. weekday 7am, sunset"],'
    '"duration_hint":"e.g. 2-3 hours or empty",'
    '"must_bring":["items the post says to pack/bring"],'
    '"must_do_tips":["strong tips: must book, arrive before X, permit required, '
    'avoid weekends, cash only, etc."],'
    '"tags":["open-vocab lowercase activity/vibe tags"]}\n'
    "Rules:\n"
    "- must_bring / must_do_tips: only explicit strong recommendations from the image.\n"
    "- If a field is unknown, use [] or \"\".\n"
    "- Max 6 places, 8 must_bring, 8 must_do_tips, 6 tags."
)


@dataclass
class Extraction:
    activity_title: str
    summary: str
    places: list[tuple[str, str]]  # (name_en, name_local)
    suggested_times: list[str]
    duration_hint: str
    must_bring: list[str]
    must_do_tips: list[str]
    tags: list[str]


def _clip_list(items, limit: int) -> list[str]:
    out: list[str] = []
    for raw in items or []:
        s = str(raw).strip()
        if s and s not in out:
            out.append(s[:120])
        if len(out) >= limit:
            break
    return out


def _parse_extraction(raw: str) -> Extraction | None:
    if not raw:
        return None
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        obj = json.loads(raw[start:end]) if start >= 0 and end > start else json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(obj, dict):
        return None

    places: list[tuple[str, str]] = []
    seen: set[str] = set()
    for it in obj.get("places") or []:
        if isinstance(it, dict):
            en = str(it.get("name_en") or it.get("name") or "").strip()
            local = str(it.get("name_local") or en).strip()
        elif isinstance(it, str):
            en = local = it.strip()
        else:
            continue
        key = (en or local).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        places.append((en or local, local or en))

    title = str(obj.get("activity_title") or "").strip()[:120]
    summary = str(obj.get("summary") or "").strip()[:280]
    if not title and not summary and not places:
        return None

    return Extraction(
        activity_title=title or (places[0][0] if places else "Saved inspiration"),
        summary=summary,
        places=places[:6],
        suggested_times=_clip_list(obj.get("suggested_times"), 6),
        duration_hint=str(obj.get("duration_hint") or "").strip()[:80],
        must_bring=_clip_list(obj.get("must_bring"), 8),
        must_do_tips=_clip_list(obj.get("must_do_tips"), 8),
        tags=_clip_list(obj.get("tags"), 6),
    )


async def _resolve_places(
    places: list[tuple[str, str]],
    *,
    origin_lat: float,
    origin_lng: float,
) -> list[InspirationPlaceOut]:
    if not places:
        return []
    resolved: list[InspirationPlaceOut] = []
    for name_en, name_local in places:
        hits = await geocode_query(name_en)
        lat = lng = 0.0
        note = ""
        if hits:
            lat = float(hits[0].get("lat") or 0)
            lng = float(hits[0].get("lng") or 0)
            note = str(hits[0].get("label") or "")
        resolved.append(
            InspirationPlaceOut(
                name=name_local or name_en,
                name_en=name_en,
                lat=lat,
                lng=lng,
                note=note[:160],
            )
        )
    _ = (origin_lat, origin_lng)  # reserved for future viewbox bias
    return resolved


def _taste_snippet_text(ext: Extraction, places: list[InspirationPlaceOut]) -> str:
    place_names = ", ".join(p.name for p in places[:3]) or ext.activity_title
    bits = [f"Wants to try: {ext.activity_title} ({place_names})."]
    if ext.summary:
        bits.append(ext.summary)
    if ext.suggested_times:
        bits.append("Best times: " + "; ".join(ext.suggested_times[:4]) + ".")
    if ext.duration_hint:
        bits.append(f"Duration: {ext.duration_hint}.")
    if ext.must_bring:
        bits.append("Must bring: " + ", ".join(ext.must_bring[:6]) + ".")
    if ext.must_do_tips:
        bits.append("Tips: " + "; ".join(ext.must_do_tips[:6]) + ".")
    if ext.tags:
        bits.append("Vibe: " + ", ".join(ext.tags[:6]) + ".")
    return " ".join(bits)[:400]


def capture_out(row: UserInspirationCapture) -> InspirationCaptureOut:
    def _loads(raw: str) -> list:
        try:
            val = json.loads(raw or "[]")
            return val if isinstance(val, list) else []
        except json.JSONDecodeError:
            return []

    places_raw = _loads(row.places_json)
    places: list[InspirationPlaceOut] = []
    for it in places_raw:
        if isinstance(it, dict):
            places.append(
                InspirationPlaceOut(
                    name=str(it.get("name") or ""),
                    name_en=str(it.get("name_en") or ""),
                    lat=float(it.get("lat") or 0),
                    lng=float(it.get("lng") or 0),
                    note=str(it.get("note") or ""),
                )
            )
    return InspirationCaptureOut(
        id=row.id,
        activity_title=row.activity_title,
        summary=row.summary,
        places=places,
        suggested_times=_loads(row.suggested_times_json),
        duration_hint=row.duration_hint,
        must_bring=_loads(row.must_bring_json),
        must_do_tips=_loads(row.must_do_tips_json),
        tags=_loads(row.tags_json),
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


async def process_screenshot(
    db: Session,
    user: User,
    *,
    image_bytes: bytes,
    mime: str,
    language: str = "en",
    origin_lat: float = 0.0,
    origin_lng: float = 0.0,
) -> InspirationCaptureOut:
    mime = (mime or "").split(";")[0].strip().lower()
    if mime not in _ALLOWED_MIME:
        raise ValueError("Unsupported image type (use JPEG, PNG, or WebP)")
    if len(image_bytes) > _MAX_BYTES:
        raise ValueError("Image too large (max 4 MB)")

    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    lang_note = "Respond with JSON only. Keep name_en geocodable; name_local may stay Chinese."
    if language.lower().startswith("zh"):
        lang_note += " summary may be Chinese."

    raw = await analyze_image_json(
        image_b64=b64,
        mime=mime,
        prompt=lang_note,
        system=_EXTRACT_SYSTEM,
        json_mode=True,
    )
    ext = _parse_extraction(raw)
    if ext is None:
        raise ValueError("Could not read activity details from this screenshot")

    places = await _resolve_places(ext.places, origin_lat=origin_lat, origin_lng=origin_lng)
    places_json = [
        {
            "name": p.name,
            "name_en": p.name_en,
            "lat": p.lat,
            "lng": p.lng,
            "note": p.note,
        }
        for p in places
    ]

    row = UserInspirationCapture(
        user_id=user.id,
        activity_title=ext.activity_title,
        summary=ext.summary,
        places_json=json.dumps(places_json, ensure_ascii=False),
        suggested_times_json=json.dumps(ext.suggested_times, ensure_ascii=False),
        duration_hint=ext.duration_hint,
        must_bring_json=json.dumps(ext.must_bring, ensure_ascii=False),
        must_do_tips_json=json.dumps(ext.must_do_tips, ensure_ascii=False),
        tags_json=json.dumps(ext.tags, ensure_ascii=False),
        extraction_json=json.dumps(
            {
                "activity_title": ext.activity_title,
                "summary": ext.summary,
                "must_bring": ext.must_bring,
                "must_do_tips": ext.must_do_tips,
            },
            ensure_ascii=False,
        ),
    )
    db.add(row)
    db.flush()

    snippet = _taste_snippet_text(ext, places)
    record_snippet(
        db,
        user,
        snippet,
        source=f"shot:{row.id}",
        weight=1.4,
        polarity=1.0,
    )
    db.commit()
    invalidate(user.id)
    return capture_out(row)
