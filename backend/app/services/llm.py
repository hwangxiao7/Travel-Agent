from __future__ import annotations

import json

import httpx

from app.config import settings
from app.services.i18n import tr


async def fetch_weather_note(lat: float, lng: float, lang: str = "en") -> str:
    from app.observability import atraced, external_api_latency_ms, record_external_failure

    async with atraced(
        "weather call",
        latency_metric=external_api_latency_ms,
        latency_labels={"api": "openweather"},
    ):
        if not settings.openweather_api_key:
            return tr("weather_default", lang)

        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": lat,
            "lon": lng,
            "appid": settings.openweather_api_key,
            "units": "imperial",
        }
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            desc = data["weather"][0]["description"]
            temp = data["main"]["temp"]
            return tr("weather_current", lang, desc=desc, temp=f"{temp:.0f}")
        except Exception:
            record_external_failure("openweather")
            return tr("weather_unavailable", lang)


def _record_token_usage(span, usage, provider: str) -> None:
    """Attach LLM token counts to the trace span + JSON log.

    Providers disagree on field names (OpenAI: prompt/completion_tokens;
    Anthropic: input/output_tokens) and OpenAI-compatible gateways may omit
    usage entirely, so every field is best-effort. Logged so the token cost of
    each prompt is measurable (and prompt-caching wins are visible via the
    cached count)."""
    if usage is None:
        return
    if provider == "anthropic":
        prompt_t = getattr(usage, "input_tokens", None)
        completion_t = getattr(usage, "output_tokens", None)
        cached_t = getattr(usage, "cache_read_input_tokens", None)
    else:
        prompt_t = getattr(usage, "prompt_tokens", None)
        completion_t = getattr(usage, "completion_tokens", None)
        details = getattr(usage, "prompt_tokens_details", None)
        cached_t = getattr(details, "cached_tokens", None) if details is not None else None
    total_t = (prompt_t + completion_t) if (prompt_t is not None and completion_t is not None) else None

    if span is not None:
        for key, val in (
            ("llm.tokens.prompt", prompt_t),
            ("llm.tokens.completion", completion_t),
            ("llm.tokens.total", total_t),
            ("llm.tokens.cached", cached_t),
        ):
            if val is not None:
                span.set_attribute(key, val)

    import logging

    logging.getLogger("travel_agent").info(
        "llm tokens "
        f"provider={provider} prompt={prompt_t} completion={completion_t} "
        f"total={total_t} cached={cached_t}",
        extra={"span": "LLM generation"},
    )


async def generate_summary(
    prompt: str,
    json_mode: bool = False,
    system: str | None = None,
    temperature: float | None = None,
) -> str:
    """Generate text from the configured LLM.

    When json_mode is True and the provider supports it, the model is constrained
    to emit a valid JSON object (grammar-constrained decoding) — important for
    small local models that otherwise produce malformed JSON.

    `system` carries the fixed role/instructions. Keeping them in the system
    message (instead of prepending to every user prompt) improves instruction
    adherence and lets providers cache the shared prefix across calls, so only
    the per-request facts count as fresh input tokens.

    `temperature` controls sampling. When left None it defaults to 0.2 for
    json_mode (structure-critical, we want determinism) and 0.7 for free prose."""
    from app.observability import atraced, llm_latency_ms, record_external_failure

    temp = temperature if temperature is not None else (0.2 if json_mode else 0.7)

    async with atraced(
        "LLM generation",
        attributes={
            "llm.json_mode": json_mode,
            "llm.provider": settings.llm_provider,
            "llm.temperature": temp,
        },
        latency_metric=llm_latency_ms,
    ) as span:
        provider = settings.llm_provider.lower()

        if provider == "template":
            return ""

        if provider == "anthropic" and settings.anthropic_api_key:
            import anthropic

            try:
                client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
                extra: dict = {}
                if system:
                    extra["system"] = system
                msg = await client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=800 if json_mode else 400,
                    temperature=temp,
                    messages=[{"role": "user", "content": prompt}],
                    **extra,
                )
                _record_token_usage(span, getattr(msg, "usage", None), "anthropic")
                block = msg.content[0]
                return block.text if hasattr(block, "text") else str(block)
            except Exception:
                record_external_failure("llm")
                return ""

        if settings.openai_api_key:
            from openai import AsyncOpenAI

            try:
                client_kwargs = {"api_key": settings.openai_api_key}
                if settings.openai_base_url:
                    client_kwargs["base_url"] = settings.openai_base_url
                client = AsyncOpenAI(**client_kwargs)
                extra = {}
                if json_mode:
                    extra["response_format"] = {"type": "json_object"}
                messages: list[dict] = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                resp = await client.chat.completions.create(
                    model=settings.openai_model,
                    max_tokens=800 if json_mode else 400,
                    temperature=temp,
                    messages=messages,
                    **extra,
                )
                _record_token_usage(span, getattr(resp, "usage", None), "openai")
                return resp.choices[0].message.content or ""
            except Exception:
                record_external_failure("llm")
                return ""

        return ""


async def analyze_image_json(
    *,
    image_b64: str,
    mime: str,
    prompt: str,
    system: str,
    json_mode: bool = True,
    temperature: float = 0.2,
) -> str:
    """Vision LLM: image + instructions → text (JSON when json_mode)."""
    from app.observability import atraced, llm_latency_ms, record_external_failure

    async with atraced(
        "LLM vision",
        attributes={"llm.provider": settings.llm_provider, "llm.mime": mime},
        latency_metric=llm_latency_ms,
    ) as span:
        provider = settings.llm_provider.lower()
        if provider == "template":
            return ""

        if provider == "anthropic" and settings.anthropic_api_key:
            import anthropic

            try:
                client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
                content: list[dict] = [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ]
                extra: dict = {}
                if system:
                    extra["system"] = system
                msg = await client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=900,
                    temperature=temperature,
                    messages=[{"role": "user", "content": content}],
                    **extra,
                )
                _record_token_usage(span, getattr(msg, "usage", None), "anthropic")
                block = msg.content[0]
                return block.text if hasattr(block, "text") else str(block)
            except Exception:
                record_external_failure("llm")
                return ""

        if settings.openai_api_key:
            from openai import AsyncOpenAI

            try:
                client_kwargs = {"api_key": settings.openai_api_key}
                if settings.openai_base_url:
                    client_kwargs["base_url"] = settings.openai_base_url
                client = AsyncOpenAI(**client_kwargs)
                extra = {}
                if json_mode:
                    extra["response_format"] = {"type": "json_object"}
                user_content: list[dict] = [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                    },
                ]
                messages: list[dict] = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": user_content})
                resp = await client.chat.completions.create(
                    model=settings.openai_model,
                    max_tokens=900,
                    temperature=temperature,
                    messages=messages,
                    **extra,
                )
                _record_token_usage(span, getattr(resp, "usage", None), "openai")
                return resp.choices[0].message.content or ""
            except Exception:
                record_external_failure("llm")
                return ""

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
