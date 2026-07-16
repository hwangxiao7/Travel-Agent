"""Activity → vibe sticker mapping (lightweight icon plane).

Surprise-me has dozens of activities; shipping one illustration each would
blow the app size. Instead we map every activity to one of a small fixed set
of vibe stickers (~10). Clients bundle the vibe set (L0/L1 warm) and may
also fetch by key from `/api/assets/{key}` into an on-device LRU cache.
"""

from __future__ import annotations

from app.services.activity_catalog import ACTIVITIES, Activity

# Fixed sticker keys — keep this list tiny on purpose.
VIBE_KEYS: tuple[str, ...] = (
    "vibe-adventure",
    "vibe-water",
    "vibe-nature",
    "vibe-scenic",
    "vibe-creative",
    "vibe-social",
    "vibe-night",
    "vibe-culture",
    "vibe-wellness",
    "vibe-food",
)

# Preference / trip stickers already bundled as core chrome (not vibes).
CORE_ICON_KEYS: tuple[str, ...] = (
    "mascot",
    "icon-national-park",
    "icon-hiking",
    "icon-city-walk",
    "icon-forest",
    "icon-beach",
    "icon-daytrip",
    "icon-weekend",
)

_TAG_TO_VIBE: tuple[tuple[str, str], ...] = (
    (("thrill", "adventure", "bucket-list", "sport"), "vibe-adventure"),
    (("water", "beach", "wildlife"), "vibe-water"),
    (("food",), "vibe-food"),
    (("wellness",), "vibe-wellness"),
    (("night", "music", "entertainment"), "vibe-night"),
    (("creative",), "vibe-creative"),
    (("culture", "cozy", "quiet"), "vibe-culture"),
    (("social", "playful", "puzzle", "friends", "nostalgic"), "vibe-social"),
    (("scenic", "photography", "romantic"), "vibe-scenic"),
    (("nature", "foraging", "outdoor", "explore", "hidden-gem", "family", "wholesome"), "vibe-nature"),
)

# Explicit overrides when tag heuristics are ambiguous.
_KEY_OVERRIDE: dict[str, str] = {
    "hot_spring": "vibe-wellness",
    "yoga": "vibe-wellness",
    "boxing": "vibe-wellness",
    "meditation": "vibe-wellness",
    "baking": "vibe-food",
    "cooking_class": "vibe-food",
    "farmers_market": "vibe-food",
    "picnic": "vibe-nature",
    "open_air_cinema": "vibe-scenic",
    "sunset_view": "vibe-scenic",
    "stargazing": "vibe-scenic",
    "bookstore_cafe": "vibe-culture",
    "museum": "vibe-culture",
    "flea_market": "vibe-culture",
    "comedy": "vibe-night",
    "live_music": "vibe-night",
    "indoor_climbing": "vibe-adventure",
    "go_kart": "vibe-adventure",
    "trampoline": "vibe-social",
    "mini_golf": "vibe-social",
}


def vibe_for_activity(activity: Activity) -> str:
    if activity.key in _KEY_OVERRIDE:
        return _KEY_OVERRIDE[activity.key]
    tags = set(activity.tags)
    for needle, vibe in _TAG_TO_VIBE:
        if tags.intersection(needle):
            return vibe
    return "vibe-nature" if not activity.indoor else "vibe-social"


def vibe_for_key(activity_key: str) -> str:
    from app.services.activity_catalog import ACTIVITY_BY_KEY

    act = ACTIVITY_BY_KEY.get(activity_key)
    if act is None:
        return "vibe-social"
    return vibe_for_activity(act)


def all_activity_vibe_map() -> dict[str, str]:
    return {a.key: vibe_for_activity(a) for a in ACTIVITIES}
