"""Merge screenshot-derived places into one canonical record per real POI.

Different posts/screenshots often name the same trail / venue differently
(KilaueaIkiOverlook vs Kilauea Iki Overlook vs 基拉韦厄). Layer B/C stores
one `InspirationPlaceNominationAgg` per canonical place, not per OCR variant.
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import InspirationPlaceNominationAgg, place_key
from app.models.schemas import InspirationPlaceOut
from app.services.geo import haversine_miles
from app.services.inspiration_geo import dest_key_for_place, geo_cell

_SLUG_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+", re.I)


def normalize_place_slug(name: str) -> str:
    """Aggressive normalize for fuzzy name match (latin + CJK kept)."""
    s = _SLUG_RE.sub("", (name or "").strip().lower())
    return s[:96]


def build_canonical_key(dest_key: str, lat: float, lng: float, name: str) -> str:
    """Stable id: geo bucket when coords exist, else normalized name slug."""
    if lat and lng:
        return f"canon:{dest_key}@{round(lat, 3)}:{round(lng, 3)}"[:220]
    slug = normalize_place_slug(name)
    return f"canon:{dest_key}:{slug or 'unknown'}"[:220]


def _token_overlap(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) >= 4 and len(b) >= 4 and (a in b or b in a):
        return True
    # Latin tokens: share a significant word
    if re.search(r"[a-z]", a):
        ta = {t for t in re.split(r"[^a-z0-9]+", a) if len(t) >= 4}
        tb = {t for t in re.split(r"[^a-z0-9]+", b) if len(t) >= 4}
        return bool(ta & tb)
    return False


def _load_aliases(raw: str) -> list[str]:
    try:
        val = json.loads(raw or "[]")
        return [str(x) for x in val if str(x).strip()] if isinstance(val, list) else []
    except json.JSONDecodeError:
        return []


def _save_aliases(names: list[str]) -> str:
    seen: list[str] = []
    for n in names:
        s = n.strip()
        if s and s not in seen:
            seen.append(s[:200])
        if len(seen) >= 12:
            break
    return json.dumps(seen, ensure_ascii=False)


def _pick_primary_name(current: str, candidates: list[str]) -> str:
    pool = [c for c in candidates if c.strip()]
    if not pool:
        return current
    # Prefer longest latin name (usually most geocodable), else longest overall.
    latin = [c for c in pool if re.search(r"[A-Za-z]", c)]
    if latin:
        return max(latin, key=len)
    return max(pool, key=len)


def find_matching_agg(
    db: Session,
    dest_key: str,
    place: InspirationPlaceOut,
) -> InspirationPlaceNominationAgg | None:
    """Find an existing aggregate for the same real-world place."""
    lat, lng = float(place.lat or 0), float(place.lng or 0)
    slug = normalize_place_slug(place.name_en or place.name)
    radius = settings.inspiration_merge_radius_miles

    rows = db.scalars(
        select(InspirationPlaceNominationAgg).where(
            InspirationPlaceNominationAgg.dest_key == dest_key
        )
    ).all()

    # 1) Exact canonical key (geo or slug)
    ckey = build_canonical_key(dest_key, lat, lng, place.name_en or place.name)
    for row in rows:
        if row.canonical_key == ckey:
            return row

    # 2) Proximity + optional name overlap
    for row in rows:
        if lat and lng and row.lat and row.lng:
            if haversine_miles(lat, lng, row.lat, row.lng) <= radius:
                row_slug = normalize_place_slug(row.place_name)
                if not slug or not row_slug or _token_overlap(slug, row_slug):
                    return row

    # 3) Strong name overlap in same region (no coords on one side)
    for row in rows:
        row_slug = normalize_place_slug(row.place_name)
        if slug and row_slug and _token_overlap(slug, row_slug):
            if lat and lng and row.lat and row.lng:
                if haversine_miles(lat, lng, row.lat, row.lng) > max(radius, 25.0):
                    continue
            return row

    return None


def merge_into_agg(
    agg: InspirationPlaceNominationAgg,
    *,
    place: InspirationPlaceOut,
    dest_display: str,
    activity_key: str,
    tags: list[str],
    summary: str,
    activity_title: str,
) -> None:
    """Merge a new sighting into an existing canonical aggregate (no new row)."""
    pname = (place.name or place.name_en or "").strip()
    aliases = _load_aliases(agg.aliases_json)
    if pname and pname not in aliases:
        aliases.append(pname)
    if agg.place_name and agg.place_name not in aliases:
        aliases.append(agg.place_name)
    agg.aliases_json = _save_aliases(aliases)
    agg.place_name = _pick_primary_name(agg.place_name, aliases + [pname])
    agg.dest_name = dest_display[:200] or agg.dest_name

    lat, lng = float(place.lat or 0), float(place.lng or 0)
    if lat and lng:
        # Running centroid (cheap incremental average)
        if agg.lat and agg.lng and agg.n_users > 0:
            n = max(agg.n_users, 1)
            agg.lat = (agg.lat * n + lat) / (n + 1)
            agg.lng = (agg.lng * n + lng) / (n + 1)
        else:
            agg.lat, agg.lng = lat, lng
        agg.geo_cell = geo_cell(agg.lat, agg.lng)

    if tags:
        old = {t for t in (agg.tags_csv or "").split(",") if t}
        agg.tags_csv = ",".join(sorted(old | set(tags[:6])))[:240]

    acts = {a for a in (agg.activity_keys_csv or "").split(",") if a}
    if activity_key:
        acts.add(activity_key)
    agg.activity_keys_csv = ",".join(sorted(acts))[:400]

    if summary and (not agg.blurb or len(summary) > len(agg.blurb or "")):
        agg.blurb = summary[:280]
    elif activity_title and not agg.blurb:
        agg.blurb = activity_title[:280]

    agg.n_mentions = (agg.n_mentions or 0) + 1


def resolve_or_create_agg(
    db: Session,
    *,
    place: InspirationPlaceOut,
    dest_display: str,
    activity_key: str,
    tags: list[str],
    summary: str,
    activity_title: str,
) -> tuple[InspirationPlaceNominationAgg, bool]:
    """Return (agg, created_new_canonical_row)."""
    dkey = dest_key_for_place(place)
    lat, lng = float(place.lat or 0), float(place.lng or 0)
    pname = (place.name or place.name_en or "").strip()
    cell = geo_cell(lat, lng) if (lat or lng) else geo_cell(0, 0)

    agg = find_matching_agg(db, dkey, place)
    if agg is not None:
        merge_into_agg(
            agg,
            place=place,
            dest_display=dest_display,
            activity_key=activity_key,
            tags=tags,
            summary=summary,
            activity_title=activity_title,
        )
        return agg, False

    ckey = build_canonical_key(dkey, lat, lng, place.name_en or pname)
    agg = InspirationPlaceNominationAgg(
        canonical_key=ckey,
        dest_key=dkey,
        dest_name=dest_display[:200],
        place_key=place_key(place.name_en or pname),
        place_name=pname,
        lat=lat,
        lng=lng,
        geo_cell=cell,
        n_users=0,
        n_mentions=1,
        tags_csv=",".join(tags[:6]),
        activity_keys_csv=activity_key,
        aliases_json=_save_aliases([pname] if pname else []),
        blurb=(summary or activity_title)[:280],
    )
    db.add(agg)
    return agg, True
