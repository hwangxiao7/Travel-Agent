"""In-process phone OTP store (mock SMS). No vendor yet — codes go to logs / DEV_CODE."""

from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass

from app.config import settings

log = logging.getLogger("travel.phone_otp")

_TTL_SEC = 300
_SEND_COOLDOWN_SEC = 60
_MAX_ATTEMPTS = 5

_CN_MOBILE = re.compile(r"^1[3-9]\d{9}$")


@dataclass
class _Slot:
    code: str
    expires_at: float
    attempts: int = 0
    last_send_at: float = 0.0


_STORE: dict[str, _Slot] = {}


def normalize_phone(raw: str) -> str:
    s = re.sub(r"[\s\-()]", "", (raw or "").strip())
    if s.startswith("0086"):
        s = "+86" + s[4:]
    if s.startswith("86") and len(s) == 13 and s[2:].isdigit():
        s = "+" + s
    if s.startswith("+86"):
        national = s[3:]
    elif s.isdigit() and len(s) == 11:
        national = s
        s = "+86" + s
    else:
        raise ValueError("Use a mainland China mobile (+86 / 11 digits)")
    if not _CN_MOBILE.match(national):
        raise ValueError("Invalid China mobile number")
    return s


def send_code(phone: str) -> int:
    """Create/store OTP. Returns expires_in seconds. Never returns the code."""
    now = time.time()
    existing = _STORE.get(phone)
    if existing and now - existing.last_send_at < _SEND_COOLDOWN_SEC:
        raise ValueError("Please wait before requesting another code")
    code = (settings.auth_phone_dev_code or "").strip()
    if not (code.isdigit() and len(code) == 6):
        code = f"{random.randint(0, 999999):06d}"
    _STORE[phone] = _Slot(code=code, expires_at=now + _TTL_SEC, attempts=0, last_send_at=now)
    # Mock SMS: log only (no vendor). Do not put code in API JSON.
    log.info("phone_otp mock send phone_tail=%s code=%s", phone[-4:], code)
    return _TTL_SEC


def verify_code(phone: str, code: str) -> bool:
    slot = _STORE.get(phone)
    if slot is None:
        return False
    now = time.time()
    if now > slot.expires_at:
        _STORE.pop(phone, None)
        return False
    slot.attempts += 1
    if slot.attempts > _MAX_ATTEMPTS:
        _STORE.pop(phone, None)
        return False
    if slot.code != code.strip():
        return False
    _STORE.pop(phone, None)
    return True
