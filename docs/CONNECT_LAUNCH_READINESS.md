# ParkPe Connect Launch Readiness Runbook

## Objective
Production launch gate for Connect chat + calling with abuse prevention, moderation operations, and quality SLO checks.

## Pre-Launch Controls
- Risk thresholds configured in environment:
  - `CONNECT_CALL_MAX_PER_USER_HOUR`
  - `CONNECT_CALL_MAX_PER_PHONE_HOUR`
  - `CONNECT_CALL_MAX_PER_OWNER_HOUR`
  - `CONNECT_CALL_MAX_PER_FINGERPRINT_HOUR`
  - `CONNECT_CALL_MAX_UNIQUE_QR_PER_HOUR`
  - `CONNECT_CHAT_MAX_PER_USER_HOUR`
  - `CONNECT_CHAT_MAX_PER_THREAD_HOUR`
  - `CONNECT_CHAT_MAX_PER_RECIPIENT_HOUR`
  - `CONNECT_CHAT_MAX_PER_FINGERPRINT_HOUR`
  - `CONNECT_CHAT_MAX_BODY_LENGTH`
- Hub console reachable at `/connect/ops/`.
- Connect moderation actions available in admin and Hub.
- Scan logging enabled with trusted proxy IP extraction.

## Abuse Simulations (Must Pass)
- **Call bombing same owner**: simulate > owner hourly threshold, expect API `429` with `connect_risk_block`.
- **Distributed caller fingerprint abuse**: keep sender user stable, rotate QR targets, expect block on unique target spread.
- **Chat flood in single thread**: exceed per-thread message threshold, expect message policy block.
- **Report gaming check**: repeated reports from same reporter should not escalate to auto-block; distinct reporters should.

## Security Tests (Must Pass)
- Expired/invalid `call_token` rejected.
- `call_token` cannot be reused after single initiation.
- Token QR binding enforced (`call_token` generated for QR-A cannot call QR-B).
- Scanner OTP brute force protection returns `429` after threshold.
- No raw owner/scanner numbers leaked in logs or response payloads.

## Reliability and UX Tests (Must Pass)
- Chat polling pauses when tab/app view hidden and resumes on focus.
- Send failure shows user-facing error (no silent failures).
- Notification sound plays only for incoming messages from other participant.
- Call initiation success/failure uses in-app toast messaging.
- Hindi locale renders predefined message labels when available.

## Operational Dashboards
- Hub page `/connect/ops/`:
  - Calls/scans/reports/active blocks snapshots
  - High-risk event stream
  - Moderation timeline
  - Policy snapshot
- JSON analytics endpoint `/connect/ops/analytics/`:
  - call success rate
  - risk block counts
  - pending reports
  - top reported users
  - top targeted owners

## Incident Response
- Temporary mitigation: reduce call/chat thresholds via env and restart.
- Manual moderation action in Hub:
  - `warn` -> increase warning count
  - `temp_block` -> set timed `connect_blocked_until`
  - `perm_block` -> long horizon block window
  - `unblock` -> immediate release
- Escalate with artifacts:
  - `ConnectCallLog`
  - `ConnectScanLog`
  - `ConnectReport`
  - `ConnectModerationAction`
  - `LogEntry` category `connect_vehicle`

## Rollback Strategy
- Disable aggressive thresholds by setting higher limits.
- Temporarily bypass step-up friction by raising call limits.
- Keep logging and moderation enabled during rollback for forensic continuity.

## Privacy, encryption, and logging (product truth)
- **In transit:** HTTPS/TLS only for clients (standard web/mobile posture).
- **At rest on servers:** Connect message `body` and `metadata` are stored as **plaintext** in the application database for delivery, search (where enabled), moderation, and support. This is **not** WhatsApp-style end-to-end encryption (E2EE). **E2EE** would be a separate initiative (key management, multi-device, recovery) if the product commits to it.
- **Notifications:** In-app and (when enabled) push payloads include **thread id**, **masked vehicle registration in the title**, and a **short text preview** — not raw phone numbers. SMS alerts follow the same high-level wording.
- **Audit / ops logs:** Treat message bodies and attachment paths as **PII/sensitive**; avoid logging full content in application or web server logs. Prefer structured IDs (`thread_id`, `message_id`) for investigations.

## Realtime transport (optional roadmap)
- **Today:** Thread messages sync via **HTTP polling** (interval + tab visibility); typing/presence use short TTL cache keys.
- **Future (medium effort):** Add **SSE** or **WebSockets** (e.g. Django Channels / ASGI) for message and presence streams to cut polling traffic and tail latency. Keep HTTP POST for sends and persist abuse/risk checks server-side unchanged.
