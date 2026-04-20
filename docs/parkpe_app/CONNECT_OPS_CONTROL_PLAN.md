# Connect Ops control tower — plan (QR, chat, call, profanity)

## Goals (user requirements)

1. **QR → next action** — Har scan ke baad kya hua: public lookup, thread bana, pehla message, call try, etc. (MVP: alag tables se timeline; full “event graph” baad mein.)
2. **QR se user onboard** — Kaun sa `qr_code` tha jis se scanner ne OTP verify karke user bana / login hua.
3. **Scan ke baad messages** — Connect chat messages (thread, sender, time, body preview).
4. **Call** — `ConnectCallLog` (success, QR, owner, time).
5. **Abuse / profanity (Hindi + English)** — Aise shabd bhejne par message **block** + user ko turant **API warning**; optional profile warning count / audit log.

## Data we already have

| Source | Use |
|--------|-----|
| `ConnectScanLog` | QR, vehicle, optional `scanned_by`, IP, time |
| `ConnectThread` + `ConnectMessage` | Scanner–owner chat; `body` for text |
| `ConnectCallLog` | QR, call success, owner, time |
| Scanner `verify-otp` | JWT; pehle `qr_code` DB mein link nahi tha |

## Phase 1 (done)

- **Model `ConnectQrOnboardLog`**: `user`, `qr_code`, `vehicle` (optional), `is_new_user`, `ip`, `created_at` — verify-otp success par jab valid `qr_code` ho.
- **Profanity filter** (text/attachment/voice body, predefined excluded): `api/connect/data/profanity_*.txt` + env `CONNECT_PROFANITY_EXTRA_TERMS`. Response `400` with `code: "connect_profanity"`; `Profile.connect_warning_count` increment; ParkPe app uses **warning** toast for that code.
- **Ops** (`/connect/ops/`): recent **onboardings**, **calls**, **chat** (text preview) + existing scans. Celery still required for `ConnectScanLog` async writes.

## Phase 2 (in progress)

- **Unified timeline** — Ops `/connect/ops/` GET form: `timeline_qr` (exact QR) or `timeline_user` (user pk); `timeline_hours` (1–720, default 168). Merges scan, onboard, call, chat (newest-first, cap 200). Implementation: `portal/services/connect_ops_timeline.py`.
- **Custom profanity files** — `CONNECT_PROFANITY_CUSTOM_FILE` (extra English tokens, same line format as `profanity_en.txt`) and `CONNECT_PROFANITY_CUSTOM_FILE_HI` (Devanagari lines). Admin UI for lists: still optional / later.
- **Repeat profanity → temp Connect block** — `CONNECT_PROFANITY_AUTO_BLOCK_THRESHOLD` (0 = off), `CONNECT_PROFANITY_AUTO_BLOCK_MINUTES`, optional `CONNECT_PROFANITY_AUTO_BLOCK_MESSAGE`. Hourly rolling counter per user; response may include `connect_temp_blocked: true`.
- **Still later** — WebSocket / push for profanity (today: HTTP + toast); optional admin UI editor for blocklists.

## Operations

- **Celery** must run for scan logs; onboard log is **synchronous** (no worker).
- Blocklist files: add words one per line; `#` comments; UTF-8 (Hindi supported).
