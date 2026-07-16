# Feature-flagged Phone + WeChat Auth (China market ready)

**Date:** 2026-07-14  
**Status:** Implemented (default feature flags OFF)  
**Scope:** Backend + Web + iOS (option C)  
**WeChat UX:** Website OAuth / QR flow shared by Web + iOS (option B — no native WeChat SDK)  
**SMS:** Full API + in-process mock codes (option A — no Aliyun/Tencent provider yet)

---

## 1. Problem

Email/password works for NA beta and demos. Mainland China users rarely use email; when we deploy there we need phone OTP and WeChat login. We want the modules built now, **off by default**, and turned on via env when entering that market.

## 2. Goals / Non-goals

### Goals

- Feature flags: `AUTH_PHONE_ENABLED`, `AUTH_WECHAT_ENABLED` (default `false`)
- Identity decoupling: a `User` may authenticate via email, phone, and/or WeChat
- `GET /api/auth/methods` so clients render only enabled methods
- Phone: send + verify OTP → JWT (same shape as today’s `AuthResponse`)
- WeChat: website OAuth start + callback → find/create user → JWT (or one-time ticket for SPA/iOS)
- Web Account UI + iOS Account UI respect `/auth/methods`
- Existing email register/login unchanged when flags are off

### Non-goals (this iteration)

- Native WeChat Open SDK / Universal Links / App Store WeChat review
- Real SMS vendor (Aliyun / Tencent) — mock only; vendor plug-in later
- Full account-merge UI (bind email + phone + WeChat for one person)
- Changing JWT algorithm or session model

## 3. Approaches considered

| Approach | Verdict |
|---|---|
| **1. Identity fields + flags + `/auth/methods`** | **Chosen** |
| 2. Fake emails (`phone_+86…@local`) | Rejected — dirty data, hard to evolve |
| 3. Separate China auth service/tables | Rejected — overkill for MVP |

## 4. Configuration

```bash
# Defaults: both false → product identical to today
AUTH_PHONE_ENABLED=false
AUTH_WECHAT_ENABLED=false

# Phone mock (only used when AUTH_PHONE_ENABLED=true)
AUTH_PHONE_DEV_CODE=        # if set, always accept this 6-digit code (device QA)
# OTP TTL ~300s, rate limit e.g. 1 send / 60s / phone

# WeChat website application (only when AUTH_WECHAT_ENABLED=true)
WECHAT_APP_ID=
WECHAT_APP_SECRET=
WECHAT_REDIRECT_URI=        # https://your-domain/api/auth/wechat/callback
```

When a flag is **off**, related endpoints return **404** (not 403), so scanners and old clients don’t treat them as “almost available.”  
When WeChat flag is **on** but AppId/Secret missing, start/callback return **503** with a clear “not configured” message.

Document placeholders in `.env.example` only — never commit real secrets.

## 5. Data model

`users` table changes (SQLite-friendly via existing `_ensure_sqlite_columns` pattern):

| Column | Change |
|---|---|
| `email` | Nullable; unique when present. Email users still require it. |
| `password_hash` | Nullable. Phone/WeChat-only users may have empty/null hash. |
| `phone` | New, nullable, unique, indexed. E.164-ish normalized string (e.g. `+8613800138000`). |
| `wechat_openid` | New, nullable, unique, indexed. |
| `wechat_unionid` | New, nullable, indexed (optional; store when WeChat returns it). |

Synthetic email for WeChat/phone-only users is **not** used.  
`UserOut` / clients: `email` may be `""`; add optional `phone` (masked in responses if desired, e.g. `138****8000`).

**Delete account:** today requires password. Extend:

- If `password_hash` present → current password flow  
- Else if phone auth enabled and user has `phone` → require OTP verify then delete  
- Else → refuse with clear error (must set password or use phone OTP) — keep simple

## 6. API

### Discovery

`GET /api/auth/methods` → always 200:

```json
{ "email": true, "phone": false, "wechat": false }
```

`email` stays `true` for this product phase.

### Phone (gated by `AUTH_PHONE_ENABLED`)

1. `POST /api/auth/phone/send` `{ "phone": "+8613…" }`  
   - Validate CN mobile format (basic: `+86` + 11 digits starting with 1, or bare 11-digit normalized to `+86`)  
   - Generate 6-digit code; store in process memory `{ phone: { code, expires_at, attempts } }`  
   - Mock: log code at INFO; if `AUTH_PHONE_DEV_CODE` set, store that code instead  
   - Response: `{ "ok": true, "expires_in": 300 }` (never return the code in JSON, even in mock — only logs / fixed env for QA)

2. `POST /api/auth/phone/verify` `{ "phone", "code", "display_name?" }`  
   - Check code + TTL + attempt cap  
   - Find user by `phone` or create (`password_hash=null`, `email=null`, display_name default from phone tail)  
   - Return `AuthResponse` (JWT + `UserOut`)

### WeChat website OAuth (gated by `AUTH_WECHAT_ENABLED`)

1. `GET /api/auth/wechat/start?return_to=`  
   - Build WeChat QR connect URL (`open.weixin.qq.com` website app OAuth) with `state`  
   - Store `state` → `return_to` (app deep link or web origin) briefly in memory  
   - Response: `{ "authorize_url": "…" }`

2. `GET /api/auth/wechat/callback?code=&state=`  
   - Exchange `code` for access_token + openid (httpx to WeChat API)  
   - Find/create user by `wechat_openid`  
   - Issue one-time `ticket` (random, ~2 min TTL) mapped to JWT  
   - Redirect to `return_to` with `?ticket=` (Web) or custom URL scheme / universal link pattern already used by app if any; for iOS without native scheme yet: redirect to a small HTTPS page or `travelagent://auth?ticket=` documented in Config  
   - Client calls `POST /api/auth/wechat/exchange` `{ "ticket" }` → `AuthResponse`

If WeChat HTTP APIs fail, surface 502 with generic message (no secret leakage).

## 7. Clients

### Shared behavior

On Account screen appear / app launch (once per session): fetch `/api/auth/methods`.  
Cache in memory. If fetch fails, assume `{ email: true, phone: false, wechat: false }`.

### Web (`AccountModal` etc.)

- Always show email register/login (current)  
- If `phone`: show phone + OTP fields calling send/verify  
- If `wechat`: button opens `authorize_url` (`window.location` or popup); landing page reads `ticket` and exchanges  

### iOS (`AccountView` / `AuthStore` / `APIClient`)

- Same methods fetch  
- Phone UI: TextField + OTP  
- WeChat: `SafariView` / `openURL` to `authorize_url`; handle return via URL with `ticket` → exchange  
  - Document a placeholder URL scheme e.g. `travelagent://auth` in Info.plist only if needed for callback; if callback is HTTPS web page that deep-links, keep minimal  

Flags off → UI identical to today.

## 8. Security notes

- Do not log full phone + code together in production-oriented log format beyond mock INFO (acceptable for local mock)  
- Rate-limit send by phone and by IP (simple in-memory)  
- OTP attempt lockout after N failures  
- JWT unchanged (`create_access_token`)  
- WeChat `state` CSRF check required  
- Feature-off → 404 on gated routes  

## 9. Testing / success criteria

1. Flags default off: email register/login works; `/auth/methods` shows phone/wechat false; phone/wechat routes 404; Web/iOS show no extra buttons  
2. `AUTH_PHONE_ENABLED=true` + `AUTH_PHONE_DEV_CODE=123456`: send → verify → JWT; user row has `phone`, null email/password  
3. WeChat flag on without credentials: start returns 503  
4. (Manual / later) WeChat with real AppId: round-trip create user by openid  

## 10. Rollout (future China deploy)

1. Obtain WeChat website app + redirect domain  
2. Set `WECHAT_*`, `AUTH_WECHAT_ENABLED=true`  
3. Plug real SMS provider (replace mock sender) + `AUTH_PHONE_ENABLED=true`  
4. Optional later: native WeChat SDK on iOS; account linking UI  

## 11. Files likely touched (implementation)

- `backend/app/config.py`, `db.py`, `models/schemas.py`  
- New: `backend/app/services/phone_otp.py`, `backend/app/services/wechat_oauth.py`  
- New or extend: `backend/app/routers/auth_china.py` (or sections in `account.py`)  
- `.env.example`, short note in README or tech doc  
- `frontend/src/api/*`, `AccountModal.tsx`  
- `ios/.../APIClient.swift`, `AuthStore.swift`, `AccountView.swift`, Info URL types if needed  

---

## Spec self-review

- No placeholder “TBD” APIs — paths and payloads named  
- Mock OTP never returned in JSON (only log / env) — explicit  
- Scope capped: no native SDK, no SMS vendor, no merge UI  
- SQLite column migration path called out  

**Next:** user reviews this file → implementation plan → code.
