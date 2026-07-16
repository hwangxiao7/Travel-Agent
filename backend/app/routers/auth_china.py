"""Feature-flagged phone OTP + WeChat website OAuth (China market ready, default off)."""

from __future__ import annotations

import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.config import settings
from app.db import User, get_db
from app.models.schemas import AuthResponse, UserOut
from app.routers.account import _user_out
from app.services import phone_otp, wechat_oauth

log = logging.getLogger("travel.auth_china")
router = APIRouter(prefix="/api/auth", tags=["auth-china"])


class AuthMethodsOut(BaseModel):
    email: bool = True
    phone: bool = False
    wechat: bool = False


class PhoneSendRequest(BaseModel):
    phone: str


class PhoneSendResponse(BaseModel):
    ok: bool = True
    expires_in: int = 300


class PhoneVerifyRequest(BaseModel):
    phone: str
    code: str = Field(min_length=4, max_length=8)
    display_name: str = ""


class WeChatStartResponse(BaseModel):
    authorize_url: str


class WeChatExchangeRequest(BaseModel):
    ticket: str


def _require_phone():
    if not settings.auth_phone_enabled:
        raise HTTPException(status_code=404, detail="Not found")


def _require_wechat():
    if not settings.auth_wechat_enabled:
        raise HTTPException(status_code=404, detail="Not found")


def _token_for(user: User) -> str:
    return create_access_token(user.id, user.email or "", user.token_version or 0)


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(access_token=_token_for(user), user=_user_out(user))


@router.get("/methods", response_model=AuthMethodsOut)
def auth_methods():
    return AuthMethodsOut(
        email=True,
        phone=bool(settings.auth_phone_enabled),
        wechat=bool(settings.auth_wechat_enabled),
    )


@router.post("/phone/send", response_model=PhoneSendResponse)
def phone_send(body: PhoneSendRequest, request: Request):
    _require_phone()
    try:
        phone = phone_otp.normalize_phone(body.phone)
        expires_in = phone_otp.send_code(phone)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # Soft IP hint in logs only (rate limit is per-phone in phone_otp).
    log.info("phone_send ip=%s phone_tail=%s", request.client.host if request.client else "-", phone[-4:])
    return PhoneSendResponse(ok=True, expires_in=expires_in)


@router.post("/phone/verify", response_model=AuthResponse)
def phone_verify(body: PhoneVerifyRequest, db: Session = Depends(get_db)):
    _require_phone()
    try:
        phone = phone_otp.normalize_phone(body.phone)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not phone_otp.verify_code(phone, body.code):
        raise HTTPException(status_code=401, detail="Invalid or expired code")
    user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        # Internal unique email placeholder (stripped in UserOut) — SQLite unique email.
        email_key = f"__phone__{phone}"
        user = User(
            email=email_key,
            phone=phone,
            display_name=(body.display_name or f"用户{phone[-4:]}").strip()[:120],
            password_hash="",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return _auth_response(user)


@router.get("/wechat/start", response_model=WeChatStartResponse)
def wechat_start(return_to: str = Query(default="/")):
    _require_wechat()
    if not wechat_oauth.wechat_configured():
        raise HTTPException(status_code=503, detail="WeChat login is not configured")
    try:
        url = wechat_oauth.begin_oauth(return_to)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return WeChatStartResponse(authorize_url=url)


@router.get("/wechat/callback")
async def wechat_callback(
    code: str = "",
    state: str = "",
    db: Session = Depends(get_db),
):
    _require_wechat()
    if not wechat_oauth.wechat_configured():
        raise HTTPException(status_code=503, detail="WeChat login is not configured")
    return_to = wechat_oauth.pop_return_to(state)
    if not return_to:
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")
    try:
        openid, unionid = await wechat_oauth.exchange_code(code)
    except Exception as exc:
        log.warning("wechat callback failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="WeChat authorization failed") from exc

    user = db.scalar(select(User).where(User.wechat_openid == openid))
    if user is None:
        user = User(
            email=f"__wx__{openid}",
            wechat_openid=openid,
            wechat_unionid=unionid or "",
            display_name=f"微信用户{openid[-4:]}",
            password_hash="",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif unionid and not (user.wechat_unionid or ""):
        user.wechat_unionid = unionid
        db.commit()

    ticket = wechat_oauth.issue_ticket(_token_for(user))
    return RedirectResponse(_append_query(return_to, {"ticket": ticket}), status_code=302)


@router.post("/wechat/exchange", response_model=AuthResponse)
def wechat_exchange(body: WeChatExchangeRequest, db: Session = Depends(get_db)):
    _require_wechat()
    jwt_token = wechat_oauth.redeem_ticket(body.ticket.strip())
    if not jwt_token:
        raise HTTPException(status_code=401, detail="Invalid or expired ticket")
    from app.auth import decode_token

    try:
        payload = decode_token(jwt_token)
        user_id = int(payload.get("sub", "0"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid ticket") from exc
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    # Re-issue a fresh JWT (ticket already consumed the intermediate one).
    return _auth_response(user)


def _append_query(url: str, extra: dict[str, str]) -> str:
    parts = urlsplit(url)
    q = dict(parse_qsl(parts.query, keep_blank_values=True))
    q.update(extra)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))
