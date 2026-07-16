"""WeChat website OAuth (QR / open.weixin.qq.com) — shared by Web + iOS Safari."""

from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from app.config import settings

log = logging.getLogger("travel.wechat_oauth")

_STATE_TTL = 600
_TICKET_TTL = 120


@dataclass
class _State:
    return_to: str
    expires_at: float


@dataclass
class _Ticket:
    access_token: str
    expires_at: float


_STATES: dict[str, _State] = {}
_TICKETS: dict[str, _Ticket] = {}


def wechat_configured() -> bool:
    return bool(settings.wechat_app_id.strip() and settings.wechat_app_secret.strip() and settings.wechat_redirect_uri.strip())


def begin_oauth(return_to: str) -> str:
    if not wechat_configured():
        raise RuntimeError("WeChat OAuth is not configured")
    state = secrets.token_urlsafe(24)
    _STATES[state] = _State(return_to=return_to or "/", expires_at=time.time() + _STATE_TTL)
    params = {
        "appid": settings.wechat_app_id.strip(),
        "redirect_uri": settings.wechat_redirect_uri.strip(),
        "response_type": "code",
        "scope": "snsapi_login",
        "state": state,
    }
    return "https://open.weixin.qq.com/connect/qrconnect?" + urlencode(params) + "#wechat_redirect"


def pop_return_to(state: str) -> str | None:
    slot = _STATES.pop(state, None)
    if slot is None or time.time() > slot.expires_at:
        return None
    return slot.return_to


async def exchange_code(code: str) -> tuple[str, str | None]:
    """Return (openid, unionid|None)."""
    if not wechat_configured():
        raise RuntimeError("WeChat OAuth is not configured")
    url = "https://api.weixin.qq.com/sns/oauth2/access_token"
    params = {
        "appid": settings.wechat_app_id.strip(),
        "secret": settings.wechat_app_secret.strip(),
        "code": code,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()
    if data.get("errcode"):
        log.warning("wechat token error errcode=%s", data.get("errcode"))
        raise RuntimeError("WeChat authorization failed")
    openid = data.get("openid")
    if not openid:
        raise RuntimeError("WeChat authorization failed")
    return str(openid), (str(data["unionid"]) if data.get("unionid") else None)


def issue_ticket(jwt_token: str) -> str:
    ticket = secrets.token_urlsafe(32)
    _TICKETS[ticket] = _Ticket(access_token=jwt_token, expires_at=time.time() + _TICKET_TTL)
    return ticket


def redeem_ticket(ticket: str) -> str | None:
    slot = _TICKETS.pop(ticket, None)
    if slot is None or time.time() > slot.expires_at:
        return None
    return slot.access_token
