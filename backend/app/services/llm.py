from __future__ import annotations

import json

import httpx

from app.config import settings


async def fetch_weather_note(lat: float, lng: float) -> str:
    if not settings.openweather_api_key:
        return "Check local forecast before you go — mountain and coastal weather can shift quickly."

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"lat": lat, "lon": lng, "appid": settings.openweather_api_key, "units": "imperial"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        return f"Current conditions: {desc}, ~{temp:.0f}°F."
    except Exception:
        return "Weather lookup unavailable — check forecast before departure."


async def generate_summary(prompt: str) -> str:
    provider = settings.llm_provider.lower()

    if provider == "template":
        return ""

    if provider == "anthropic" and settings.anthropic_api_key:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        msg = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        block = msg.content[0]
        return block.text if hasattr(block, "text") else str(block)

    if settings.openai_api_key:
        from openai import AsyncOpenAI

        client_kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        client = AsyncOpenAI(**client_kwargs)
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""

    return ""


async def chat_reply(prompt: str) -> str:
    text = await generate_summary(prompt)
    if text:
        return text
    return (
        "I can adjust your trip right now — try: \"make it closer\", \"switch to a "
        "different destination\", \"more relaxed pace\", \"pack in more stops\", or "
        "\"make it family-friendly\". (Add your own OpenAI/Anthropic key for open-ended chat.)"
    )


def parse_itinerary_json(raw: str) -> dict | None:
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except json.JSONDecodeError:
        return None
    return None
