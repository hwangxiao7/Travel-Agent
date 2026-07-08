from __future__ import annotations

import json

import httpx

from app.config import settings
from app.services.i18n import tr


async def fetch_weather_note(lat: float, lng: float, lang: str = "en") -> str:
    if not settings.openweather_api_key:
        return tr("weather_default", lang)

    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"lat": lat, "lon": lng, "appid": settings.openweather_api_key, "units": "imperial"}
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        desc = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        return tr("weather_current", lang, desc=desc, temp=f"{temp:.0f}")
    except Exception:
        return tr("weather_unavailable", lang)


async def generate_summary(prompt: str, json_mode: bool = False) -> str:
    """Generate text from the configured LLM.

    When json_mode is True and the provider supports it, the model is constrained
    to emit a valid JSON object (grammar-constrained decoding) — important for
    small local models that otherwise produce malformed JSON."""
    provider = settings.llm_provider.lower()

    if provider == "template":
        return ""

    if provider == "anthropic" and settings.anthropic_api_key:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        msg = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=800 if json_mode else 400,
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
        extra: dict = {}
        if json_mode:
            extra["response_format"] = {"type": "json_object"}
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            max_tokens=800 if json_mode else 400,
            messages=[{"role": "user", "content": prompt}],
            **extra,
        )
        return resp.choices[0].message.content or ""

    return ""


def parse_itinerary_json(raw: str) -> dict | None:
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
    except json.JSONDecodeError:
        return None
    return None
