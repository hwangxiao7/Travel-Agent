from __future__ import annotations

LANG_NAME = {"en": "English", "zh": "Simplified Chinese"}


def lang_name(lang: str) -> str:
    return LANG_NAME.get(lang, "English")


# Packing tips keyed by canonical id.
PACK: dict[str, dict[str, str]] = {
    "water": {"en": "Water bottle", "zh": "水壶"},
    "snacks": {"en": "Snacks", "zh": "零食"},
    "charger": {"en": "Phone charger / battery pack", "zh": "充电宝"},
    "trail_shoes": {"en": "Trail shoes", "zh": "徒步鞋"},
    "rain_layer": {"en": "Light rain layer", "zh": "轻便雨衣"},
    "sunscreen": {"en": "Sunscreen", "zh": "防晒霜"},
    "sandals": {"en": "Sandals or water shoes", "zh": "凉鞋或涉水鞋"},
    "overnight": {"en": "Overnight bag", "zh": "过夜行李"},
    "toiletries": {"en": "Toiletries", "zh": "洗漱用品"},
    "warm_layer": {"en": "Warm layer for evenings", "zh": "夜间保暖外套"},
}


def pack(key: str, lang: str) -> str:
    entry = PACK.get(key, {})
    return entry.get(lang) or entry.get("en") or key


# Templated messages for summaries, refiner replies, and weather notes.
MSG: dict[str, dict[str, str]] = {
    "summary_fallback": {
        "en": "Head to {name} — {highlight} About {time} drive from your starting point.",
        "zh": "出发去 {name} —— {highlight} 距出发点约 {time} 车程。",
    },
    "switch_summary": {
        "en": "Switched to {name} — {highlight} About {time} drive from {origin}.",
        "zh": "已切换到 {name} —— {highlight} 距 {origin} 约 {time} 车程。",
    },
    "relaxed_summary": {
        "en": "Relaxed pace: later start and fewer stops so you're not rushing.",
        "zh": "轻松节奏：推迟出发、减少站点，不赶时间。",
    },
    "busier_summary": {
        "en": "Packed the day with more stops to make the most of the trip.",
        "zh": "把当天排得更满，充分利用行程。",
    },
    "family_summary": {
        "en": "Family-friendly pick: {name} — {highlight}",
        "zh": "适合家庭的选择：{name} —— {highlight}",
    },
    "closer_reply": {
        "en": "Here's a closer option: {name} ({time} drive). {highlight}",
        "zh": "给你换了个更近的：{name}（车程 {time}）。{highlight}",
    },
    "different_reply": {
        "en": "Here's a different destination: {name} ({time} drive). {highlight}",
        "zh": "给你换了个新目的地：{name}（车程 {time}）。{highlight}",
    },
    "no_other": {
        "en": "I couldn't find another destination within range. Try widening your preferences.",
        "zh": "这个范围内没有其他目的地了，试试放宽偏好或驾车时间。",
    },
    "relaxed_reply": {
        "en": "Slowed it down — later start (10:30) and trimmed to the top stops each day.",
        "zh": "已放慢节奏——推迟到 10:30 出发，每天只保留最值得的几站。",
    },
    "busier_reply": {
        "en": "Added more to your {name} day — a fuller itinerary with extra stops.",
        "zh": "给 {name} 这天加了更多安排——行程更丰富了。",
    },
    "busier_fail": {
        "en": "I can't add more here right now.",
        "zh": "这里暂时没法再增加安排了。",
    },
    "family_reply": {
        "en": "For a family trip I'd suggest {name} — easier terrain and a gentle pace.",
        "zh": "家庭出行我推荐 {name}——路线更好走、节奏更舒缓。",
    },
    "no_plan": {
        "en": "Generate a plan first, then I can make it closer, more relaxed, busier, or switch the destination.",
        "zh": "请先生成一个计划，然后我可以帮你换近一点、更轻松、更丰富，或者换目的地。",
    },
    "tell_me": {
        "en": "Tell me how you'd like to adjust the trip.",
        "zh": "告诉我你想怎么调整行程。",
    },
    "capabilities": {
        "en": (
            'I can adjust your trip right now — try: "make it closer", '
            '"switch to a different destination", "more relaxed pace", '
            '"pack in more stops", or "make it family-friendly". '
            "(Add your own OpenAI/Anthropic key for open-ended chat.)"
        ),
        "zh": (
            "我现在就能帮你改行程——试试：「换近一点」「换个目的地」「轻松一点」"
            "「多加些安排」或「适合家庭」。（配置你自己的 OpenAI/Anthropic key 后可自由对话。）"
        ),
    },
    "weather_default": {
        "en": "Check local forecast before you go — mountain and coastal weather can shift quickly.",
        "zh": "出发前查一下当地天气——山区和海边天气变化快。",
    },
    "weather_current": {
        "en": "Current conditions: {desc}, ~{temp}°F.",
        "zh": "当前天气：{desc}，约 {temp}°F。",
    },
    "weather_unavailable": {
        "en": "Weather lookup unavailable — check forecast before departure.",
        "zh": "天气查询暂不可用——出发前请自行查看预报。",
    },
}


def tr(key: str, lang: str, **kwargs) -> str:
    entry = MSG.get(key, {})
    template = entry.get(lang) or entry.get("en") or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template
