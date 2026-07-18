"""Local OCR for screenshot inspiration — no vision LLM tokens.

Uses RapidOCR (ONNX) for Chinese + English UI text. Lazy-loaded so servers
that only use vision fallback pay no import cost until first OCR call.
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger("travel_agent")

_engine = None
_engine_failed = False


def _get_engine():
    global _engine, _engine_failed
    if _engine is not None:
        return _engine
    if _engine_failed:
        return None
    try:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
        return _engine
    except Exception as exc:
        _engine_failed = True
        logger.warning("screenshot OCR unavailable: %s", exc)
        return None


def extract_text_from_screenshot(image_bytes: bytes) -> str:
    """Return newline-joined OCR text, or \"\" if OCR unavailable / empty."""
    engine = _get_engine()
    if engine is None:
        return ""

    try:
        from PIL import Image
        import numpy as np

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        result, _ = engine(np.array(img))
    except Exception as exc:
        logger.warning("screenshot OCR failed: %s", exc)
        return ""

    if not result:
        return ""

    lines: list[str] = []
    for item in result:
        if not item or len(item) < 2:
            continue
        text = str(item[1]).strip()
        if text:
            lines.append(text)
    return "\n".join(lines)
