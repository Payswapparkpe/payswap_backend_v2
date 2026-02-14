# BBPS UAT Checklist – Required Logs & Explanations – Response

This document maps **Mobikwik BBPS UAT checklist requirements** (from `docs/MOBIKWIK_BBPS_INTEGRATION.md` and typical partner UAT docs) to our implementation and provides standard responses for submission.

---

## 1. Request body logging (encrypted + decrypted)

**Requirement:** For every API where request body is required, partners must log for UAT:
- Request body with **both** encrypted and decrypted values: `encryptedSessionKey`, `encryptedPayload`, `keyVersion`, `iv`.

| Condition | Status | Explanation |
|-----------|--------|-------------|
| Log decrypted (plain) request body | **Yes** (when UAT flag on) | When `MOBIKWIK_BBPS_UAT_VERBOSE_LOG=True`, we persist the **sanitized** plain payload to LogEntry as `request_body_plain_sanitized` (PII/secrets redacted). |
| Log encrypted request body (encryptedSessionKey, encryptedPayload, keyVersion, iv) | **Yes** (when UAT flag on) | When UAT verbose is on and encryption is used, we store `request_body_encrypted_summary` in LogEntry with key names and value **lengths** (no raw payload). |

**Response for UAT submission:**

> **Request body (encrypted + decrypted):** When `MOBIKWIK_BBPS_UAT_VERBOSE_LOG=True`, every Mobikwik BBPS API call (Token, Balance, Validation, View Bill, Recharge, Transaction Status, Operators) writes a LogEntry with: (1) **Decrypted:** `request_body_plain_sanitized` – plain JSON with `clientSecret`, `token`, `customerId`/`cn`/`refId` redacted. (2) **Encrypted:** `request_body_encrypted_summary` – keys `encryptedSessionKey`, `encryptedPayload`, `keyVersion`, `iv` with value lengths (no raw payload). UAT readiness is toggled by this env var; default is `False` for production.

---

## 2. Complete cURL, URL, request body, response per API

**Requirement:** Complete cURL (including headers), request URL, request body, response for:
- Token (success/fail)
- Balance Check (success/fail)
- Validation (success/fail)
- View Bill (success/fail)
- Recharge (success/fail/pending)
- Transaction Status (success/fail/pending)

| API | cURL / URL / body / response logged? | Status | Where in code |
|-----|--------------------------------------|--------|----------------|
| Token | Yes (when UAT flag on) | **Yes** | `mobikwik.py` – `get_token()` creates LogEntry with `request_url`, `request_body_plain_sanitized`, `response_status_code`, `response_body_truncated_sanitized`, `curl_template`. |
| Balance Check | Yes (when UAT flag on) | **Yes** | Same – `_request(..., action="balance_check")` writes full request/response and cURL to LogEntry. |
| Validation | Yes (when UAT flag on) | **Yes** | Same – `action="validation"`. |
| View Bill | Yes (when UAT flag on) | **Yes** | Same – `action="view_bill"`. |
| Recharge | Yes (when UAT flag on) | **Yes** | Same – `action="recharge"`. |
| Transaction Status | Yes (when UAT flag on) | **Yes** | Same – `action="transaction_status"`. |
| Operators | Yes (when UAT flag on) | **Yes** | Same – `action="operators"`. |

**Response for UAT submission:**

> **Complete cURL, URL, request body, response:** When `MOBIKWIK_BBPS_UAT_VERBOSE_LOG=True`, every Mobikwik BBPS API call writes a LogEntry (category `mobikwik_bbps`) with: `request_url`, `request_method`, `request_body_plain_sanitized`, `request_body_encrypted_summary` (when encryption is used), `response_status_code`, `response_body_truncated_sanitized`, and `curl_template` (reproducible cURL with sensitive headers/values replaced by `***`). On retry (timeout/5xx), `extra_data.attempts` contains both attempt_1 and attempt_2 request/response summaries.

---

## 3. Handling of pending, timeout, retry, token expiry

**Requirement:** Handling of pending, timeout, retry/status-check interval, and token expiry.

| Condition | Status | Explanation |
|-----------|--------|-------------|
| Token expiry | **Yes** | We refresh token before expiry using `_token_expires_at` and re-call `get_token()` when needed (`_ensure_token()`). Token failure is returned to caller with a clear error message. |
| Timeout | **Yes** | `httpx.Client(timeout=30.0)`; on `TimeoutException` we return `success: False`, `error: "Request timeout"`, `error_code: "TIMEOUT"` and log a warning. |
| Pending / status check | **Partial** | Recharge/Transaction Status can return pending; we pass through vendor response. We do not auto-retry or poll at a fixed interval – the client (ParkPe app or partner) can call payment status by ref_id. |
| Retry | **Yes** (when retry flag on) | When `MOBIKWIK_BBPS_RETRY_ON_FAILURE=True` (default), we retry **once** after 2s on timeout or 5xx. Both attempts are logged in LogEntry when UAT verbose is on. |

**Response for UAT submission:**

> **Token expiry:** Token is obtained via Token Generation API and reused. We refresh before expiry (using expiry time from response when provided). If token fails, we return a clear error and do not call the downstream API.  
> **Timeout:** All Mobikwik HTTP calls use a 30s timeout. On timeout we return an error and log it; when `MOBIKWIK_BBPS_RETRY_ON_FAILURE=True` we retry once after 2s.  
> **Pending:** Recharge and Transaction Status responses are returned as-is (success/fail/pending). Clients can poll Transaction Status by ref_id.  
> **Retry:** We implement one automatic retry on timeout or 5xx when `MOBIKWIK_BBPS_RETRY_ON_FAILURE=True`. Both attempts are stored in LogEntry when `MOBIKWIK_BBPS_UAT_VERBOSE_LOG=True`.

---

## 4. Auth and access control

**Requirement:** APIs should be protected; only authenticated/authorized callers can use BBPS.

| Condition | Status | Explanation |
|-----------|--------|-------------|
| ParkPe BBPS (categories, operators, fetch-bill, pay) | **Yes** | All require JWT auth (`IsAuthenticated` + `JWTAuthentication`). Unauthenticated requests get 401. |
| API v2 BBPS (partners) | **Yes** | All require API key and service permission `bbps` (operators, fetch_bill, pay_bill, payment_status). |

**Response for UAT submission:**

> All BBPS APIs require successful authentication. ParkPe app uses JWT; partner API uses API key with BBPS permissions. Unauthorized requests receive 401/403.

---

## 5. LogEntry / structured logs for BBPS

| Condition | Status | Where |
|-----------|--------|--------|
| API v2 BBPS – LogEntry per call | **Yes** | `api/v2/bbps_views.py` – `_log_bbps_api()` creates `LogEntry` with category `mobikwik_bbps` or `euronet_bbps`, action, success, message, extra_data (category, operator_id, ref_id, etc.), URL, client_ip, user_agent. |
| ParkPe BBPS – application logger | **Yes** | `api/bbps_parkpe/views.py` – `logger.info` / `logger.warning` with extra_data for categories, operators, fetch_bill, pay (count, operator_id, message). Not stored in LogEntry table. |
| Portal test BBPS – LogEntry | **Yes** | `portal/views/legacy.py` – `_create_bbps_log_entry()` for portal test panel. |

**Response for UAT submission:**

> We maintain structured logs for BBPS: (1) **API v2 (partners):** Every operators, fetch_bill, pay_bill, and payment_status call is logged to `LogEntry` with category (mobikwik_bbps/euronet_bbps), action, success/fail, message, and non-sensitive extra_data. (2) **ParkPe app:** Same operations are logged via application logger with request context. (3) **Portal test UI:** BBPS test actions create LogEntry. Logs can be filtered by category for UAT verification.

---

## 6. Sample responses for UAT (success/fail)

Use these as standard “response” text for each API in the checklist.

### Token (success)

> **Token – Success:** Request: POST to `{base_url}/recharge/v1/verify/retailer` (or configured token path) with body `{"clientId":"...","clientSecret":"..."}`. Response: 200, JSON with token and expiry. We store the token and use it in Authorization header for subsequent calls. Logged at application level on failure only.

### Token (fail)

> **Token – Fail:** On non-200 or missing token in response we return and log an error (e.g. "Failed to obtain Mobikwik BBPS token", with underlying message). No downstream API is called.

### Balance Check (success/fail)

> **Balance Check:** Called via BBPSService when needed (e.g. dashboard). Request: POST to balance path with optional merchantId. Response: success with balance data or error. Result is not persisted in LogEntry; optional to add for UAT.

### View Bill / Fetch Bill (success)

> **View Bill / Fetch Bill – Success:** Request: POST to View Bill path with body containing cn, op, cir, adParams. Response: 200 with bill details. We map to our API response (amount, billNumber, dueDate, etc.). LogEntry (API v2) or logger (ParkPe) records success with operator_id and action fetch_bill.

### View Bill / Fetch Bill (fail)

> **View Bill / Fetch Bill – Fail:** On 4xx/5xx or error in response we return 502 with vendor message. LogEntry (API v2) or logger records failure with message and operator_id.

### Recharge / Pay (success/fail/pending)

> **Recharge – Success/Fail/Pending:** Request: POST to recharge path with operatorId, customerId, amount, refId, etc. Response: success with transaction_id/status or error. We return status to client. LogEntry (API v2) or logger records pay_bill success/fail with operator_id and ref_id. Pending is passed through; client may poll Transaction Status.

### Transaction Status (success/fail/pending)

> **Transaction Status – Success/Fail/Pending:** Request: POST with refId. Response: status and optional data. We return as-is. LogEntry (API v2) records payment_status with ref_id and status.

---

## 7. Summary – conditions fulfilled

| # | Condition | Fulfilled |
|---|-----------|-----------|
| 1 | Request body logged (encrypted + decrypted) | **Yes** when `MOBIKWIK_BBPS_UAT_VERBOSE_LOG=True` (sanitized plain + encrypted summary) |
| 2 | Complete cURL, URL, body, response per API | **Yes** when `MOBIKWIK_BBPS_UAT_VERBOSE_LOG=True` (LogEntry per API with curl_template and response) |
| 3 | Token expiry handling | Yes |
| 3 | Timeout handling | Yes |
| 3 | Pending / status check | Partial – pass-through, client can poll |
| 3 | Retry | **Yes** when `MOBIKWIK_BBPS_RETRY_ON_FAILURE=True` (one retry on timeout/5xx; both attempts logged if UAT verbose on) |
| 4 | Auth required for all BBPS APIs | Yes |
| 5 | Structured logs (LogEntry / logger) | Yes for API v2 and ParkPe |

**UAT readiness:** Set `MOBIKWIK_BBPS_UAT_VERBOSE_LOG=True` and (optionally) `MOBIKWIK_BBPS_RETRY_ON_FAILURE=True` in `.env` for UAT/onboarding. Leave UAT_VERBOSE_LOG `False` in production.

---

## 8. Implementation note

The following are implemented in code:

1. **UAT verbose logging** (`MOBIKWIK_BBPS_UAT_VERBOSE_LOG`): In `portal/services/vendors/mobikwik.py`, every Token and `_request()` call (Balance, Validation, View Bill, Recharge, Transaction Status, Operators) writes a LogEntry with request URL, method, sanitized plain body, encrypted summary (when used), response status/body (truncated and sanitized), and cURL template. No secrets or full PII are stored.

2. **cURL template:** Stored in `extra_data.curl_template` for each call so support can reproduce the request.

3. **Retry** (`MOBIKWIK_BBPS_RETRY_ON_FAILURE`): One retry after 2s on timeout or 5xx. When UAT verbose is on, `extra_data.attempts` contains both attempt_1 and attempt_2 request/response summaries.
