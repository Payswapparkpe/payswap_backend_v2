# Payswap – Self-Audit Report

**Document type:** Security & architecture self-audit  
**Scope:** Entire codebase and [TECHNICAL_DOCUMENTATION.md](./TECHNICAL_DOCUMENTATION.md)  
**Severity legend:** LOW | MEDIUM | HIGH

---

## 1. Missing or Weak Business Logic

### 1.1 Payment Initiate (API v2) is a Placeholder

**Why it is a problem:**  
`POST /api/v2/payments/initiate/` returns a fake payment_id and placeholder URLs. Partners may integrate expecting real Cashfree PG flow; money is never collected, and refund/status endpoints are not backed by real gateway state. This creates contractual and compliance risk.

**Severity:** HIGH  

**Fix approach:**  
- Implement real Cashfree PG (or configured gateway) flow in PaymentInitiateView: create order with gateway, persist payment record (e.g. new Payment or Order model) linked to partner and reference_id.  
- Implement webhook handler for gateway callbacks and update payment status.  
- Ensure refund and status views read from persisted payment state and, where appropriate, call gateway APIs.  
- Add end-to-end tests and document idempotency (see Security Gaps).

---

### 1.2 Partner Charging After Voucher/KYC – No Rollback on Later Failure

**Why it is a problem:**  
Flow is: perform voucher issue (or KYC verification) → then charge partner wallet. If charging fails (e.g. insufficient balance), the voucher is already issued (or KYC already performed). There is no compensating reversal (e.g. cancel voucher or mark as “pending settlement”). Partner gets service without paying; reconciliation becomes manual.

**Severity:** MEDIUM  

**Fix approach:**  
- Define policy: either “charge first” (reserve/debit before issuing) or “issue then charge with guaranteed follow-up” (e.g. negative balance allowed with strict settlement + dunning).  
- Prefer: reserve/debit partner wallet (or check balance and hold) inside the same transaction as voucher creation where possible; if charge fails, roll back issuance.  
- If “issue then charge” is kept: persist a “pending_charge” or “unbilled_usage” record and have a periodic job (or sync path) that retries charging and alerts on repeated failure; consider admin dashboard for unbilled usage.

---

### 1.3 KYC Portal Upload – No Server-Side File Size or Type Enforcement

**Why it is a problem:**  
Template says “Max 5MB per file” and form uses `accept='image/*,.pdf'`, but the KYC submit view does not validate file size or content type before passing files to storage. Large or malicious files can be uploaded; only client-side and S3 limits (if any) apply.

**Severity:** MEDIUM  

**Fix approach:**  
- In KYC submit view (or in a shared validator), before uploading: validate each file size (e.g. max 5MB), validate extension and optionally magic bytes for allowed types (e.g. image/*, PDF). Reject with clear error if invalid.  
- Apply the same pattern to other document upload flows (e.g. brand onboarding) where only client-side or no validation exists.

---

### 1.4 Reseller Partner Wallet Creation Not Enforced

**Why it is a problem:**  
`charge_partner_for_service` assumes `partner.wallet` exists and raises if missing. There is no enforced flow that creates a wallet when a partner is approved or first uses a chargeable API. Partners may be approved without a wallet, leading to repeated runtime errors.

**Severity:** MEDIUM  

**Fix approach:**  
- On partner onboarding approval (or on first chargeable API call), ensure wallet is created if missing (e.g. get_or_create_wallet for partner).  
- Document that every ACTIVE partner must have a wallet before using chargeable services; add admin check or migration to backfill wallets for existing partners.

---

### 1.5 Assumption “Partner Has Pricing” – Fallback to Full Amount

**Why it is a problem:**  
When charging for voucher issue, if `ResellerPartnerPricing` is not found, code falls back to charging the voucher amount. Pricing is then implicit and may not match commercial terms; margins and audit trail are unclear.

**Severity:** LOW  

**Fix approach:**  
- Do not charge when no pricing is configured; return a clear error (e.g. “Partner pricing not configured for this service”) and require admin to set pricing before partner can use chargeable APIs.  
- Alternatively, define a single “default pricing” per service and use that only when explicitly configured, with audit log when default is used.

---

## 2. Security Gaps

### 2.1 No Idempotency Keys on Financial APIs

**Why it is a problem:**  
Voucher issue/redeem, partner charge, payment initiate, and BBPS pay do not accept or enforce idempotency keys (e.g. `X-Idempotency-Key` or `idempotency_key` in body). Duplicate requests (retries, double-clicks, network replays) can cause double issuance, double redemption, or double charge. Fintech standards (e.g. PCI, partner agreements) typically require idempotency for money-moving operations.

**Severity:** HIGH  

**Fix approach:**  
- Add optional `X-Idempotency-Key` (or equivalent) to: voucher issue (single and bulk create), voucher redeem (PIN/OTP), partner-charging paths, payment initiate, BBPS pay.  
- Store idempotency key + scope (e.g. partner_id + key) in DB or cache with TTL (e.g. 24h). On first request: perform operation and store result; on duplicate key: return same response without re-executing.  
- Document idempotency in API docs and require it for production partners for financial endpoints.

---

### 2.2 Voucher Redemption – Duplicate Protection Only When transaction_ref Is Sent

**Why it is a problem:**  
Duplicate redemption is avoided only when the client sends `transaction_ref` and it is unique. API v2 redeem views do not require or encourage `transaction_ref`; many clients may not send it. Without it, two identical redeem requests can both succeed (double-spend).

**Severity:** HIGH  

**Fix approach:**  
- For API v2 redeem (PIN and OTP): require `idempotency_key` or `transaction_ref` (or both; treat idempotency_key as internal and transaction_ref as partner reference). Reject requests without it, or document that duplicate requests are possible if not sent.  
- In voucher service: when neither is provided, consider rejecting in API context; in portal/UI context, consider generating a server-side idempotency token from session/request so at least same-user double-clicks are deduplicated.

---

### 2.3 Partner Wallet Debit Without Atomicity or Lock

**Why it is a problem:**  
`PartnerAccountingService.charge_partner_for_service` reads wallet balance, then updates balance and creates WalletTransaction and ResellerPartnerTransaction outside a single DB transaction and without `select_for_update`. Under concurrency, two requests can both see the same balance and both debit, leading to negative balance or inconsistent ledger.

**Severity:** HIGH  

**Fix approach:**  
- Wrap the entire charge flow (read wallet, check balance, debit wallet, create WalletTransaction, create ResellerPartnerTransaction) in a single `transaction.atomic()` block.  
- Inside it, load wallet with `Wallet.objects.select_for_update().get(id=wallet.id)` (or partner.wallet_id) so concurrent charges serialize on the same wallet row.  
- Re-check balance after lock and fail with “Insufficient balance” if amount > balance.

---

### 2.4 Voucher Redemption Without Row Lock

**Why it is a problem:**  
In `redeem_voucher_pin` and `redeem_voucher_otp`, the voucher row is read with `validate_voucher_code` (plain get). Update happens inside `transaction.atomic()` but without `select_for_update()` on the voucher. Two concurrent redemptions can both read the same `current_balance`, both compute balance_after, and both commit – enabling double-spend.

**Severity:** HIGH  

**Fix approach:**  
- Inside the existing `transaction.atomic()` block, re-fetch the voucher with `GiftVoucher.objects.select_for_update().get(id=voucher.id)` (or by voucher_code) so the row is locked for the duration of the update and transaction insert.  
- Re-validate balance and status after lock (status could have changed since initial read).

---

### 2.5 API v2 Public/Health Endpoints – No Abuse Control

**Why it is a problem:**  
`/api/v2/health/` and `/api/v2/public/` are unauthenticated. If they are hit at very high rate, they can consume resources and obscure real abuse. Rate limiting is applied per API key; unauthenticated paths may only be limited by global Django/DRF throttles (e.g. anon 100/hour), which may be too high for a single IP or bot.

**Severity:** LOW  

**Fix approach:**  
- Apply a strict global throttle (or IP-based throttle) to unauthenticated v2 endpoints (e.g. health, public).  
- Consider not logging every health check at INFO level to reduce log volume and task queue load.

---

### 2.6 Rate Limits Are High and Not Tuned Per Risk

**Why it is a problem:**  
Service-level defaults (e.g. voucher 1000/min, payment 2000/min) and per-key default (100/min, 1000/hour) are generous. A single compromised API key could burn through partner balance (voucher issue, KYC) or cause high vendor cost (SMS, KYC) before detection. No distinction between “high risk” (issue, redeem, pay) and “low risk” (balance, status) endpoints.

**Severity:** MEDIUM  

**Fix approach:**  
- Define lower default rate limits for money-moving or high-cost operations (voucher issue, redeem, KYC, payment initiate, SMS send).  
- Allow override per API key (already supported via rate_limit JSON) and document recommended limits per use case.  
- Optionally add per-endpoint or per-action throttles (e.g. voucher issue 60/min per key) in addition to global key throttle.

---

## 3. Data Integrity Risks

### 3.1 Partner Wallet Update Not Atomic With Transaction Records

**Why it is a problem:**  
In `charge_partner_for_service`, wallet balance is updated and `WalletTransaction.objects.create` is called, then `record_transaction` creates `ResellerPartnerTransaction`. There is no `transaction.atomic()` and no row lock. A crash or error between wallet save and record_transaction could leave balance debited but no ResellerPartnerTransaction (or the reverse if order were changed), breaking audit and reconciliation.

**Severity:** HIGH  

**Fix approach:**  
- Same as 2.3: single `transaction.atomic()` block for the whole charge flow, with `select_for_update()` on the wallet. Create both WalletTransaction and ResellerPartnerTransaction inside the same block so either all persist or none.

---

### 3.2 WalletService Expects WalletTransaction Fields That May Not Exist

**Why it is a problem:**  
`WalletService.add_funds` and `deduct_funds` call `WalletTransaction.objects.create(..., description=..., reference_id=..., metadata=..., performed_by=...)`. The `WalletTransaction` model in the codebase only has `reference` (and no description, reference_id, metadata, performed_by). If the running DB schema matches the model, these creates will raise and wallet operations will fail.

**Severity:** HIGH (if schema matches model) / LOW (if a migration or alternate model exists elsewhere)

**Fix approach:**  
- Align model and service: either add migration to add `description`, `reference_id`, `metadata`, `performed_by` to WalletTransaction (and use them for audit), or change WalletService to use only existing fields (e.g. put description/reference_id into `reference` or `encrypted_details`).  
- After alignment, add a simple test that creates a WalletTransaction via WalletService and asserts balance and record consistency.

---

### 3.3 Bulk Voucher Task – Batch Lock vs. Progress Persistence

**Why it is a problem:**  
Bulk task uses `select_for_update()` on the batch row to prevent two workers processing the same batch. Progress (e.g. successful_vouchers, failed_vouchers, metadata) is saved periodically (e.g. every 10 rows) and on completion. If the task is killed after updating in-memory counters but before the next save, progress is lost and a retry might re-process some rows (e.g. re-issue vouchers for same rows if not strictly idempotent per row).

**Severity:** MEDIUM  

**Fix approach:**  
- Make row-level processing idempotent: e.g. for each row, check a unique key (e.g. batch_id + row_number or voucher_code if already created) in metadata or in GiftVoucher; skip or return existing result if already processed.  
- Persist progress more frequently (e.g. after every row, or every 1–2 rows) so retries do not re-run many rows.  
- Consider storing “last_processed_row” or a list of completed row IDs in batch metadata so retry can resume exactly.

---

### 3.4 Voucher Redemption – No select_for_update on GiftVoucher

**Why it is a problem:**  
Already covered under 2.4; listed here as data integrity: concurrent redemptions can make balance and transaction history inconsistent (e.g. two REDEMPTION records, balance only decreased once).

**Severity:** HIGH  

**Fix approach:**  
- As in 2.4: use `select_for_update()` on the voucher row inside the redemption transaction.

---

## 4. Scalability Concerns

### 4.1 Every Request Enqueues a Log Task

**Why it is a problem:**  
RequestLoggingMiddleware calls `write_logs_task.delay(...)` for every non-excluded request, including request/response bodies. Under high traffic this produces a large number of Celery tasks; Redis queue and workers can become the bottleneck. Large bodies or many concurrent users multiply the effect.

**Severity:** MEDIUM  

**Fix approach:**  
- Reduce volume: e.g. do not log request/response body for every request; log body only for 4xx/5xx or for specific paths (e.g. payment, voucher issue).  
- Or log synchronously to a buffer/file and have a single periodic task batch-insert to DB or rotate files, instead of one Celery task per request.  
- Consider sampling (e.g. 1% of 2xx) for high-traffic health or public endpoints.

---

### 4.2 Bulk Voucher Processing – Single Task per Batch

**Why it is a problem:**  
One Celery task processes the entire batch sequentially. A 10k-voucher batch keeps one worker busy for a long time; other batches wait in the queue. There is no chunking or fan-out (e.g. sub-tasks per 500 rows) so throughput is limited by single-task runtime and worker count.

**Severity:** MEDIUM  

**Fix approach:**  
- Split batch into chunks (e.g. 500–1000 rows per chunk); enqueue one task per chunk with batch_id and offset/limit (or row range). A coordinator task or the API can enqueue chunks.  
- Ensure chunk tasks are idempotent and update batch progress in a thread-safe way (e.g. atomic counter or append-only metadata).  
- Keep a single “batch status” record updated by chunks so the API can still return overall progress.

---

### 4.3 Log and LogEntry Growth

**Why it is a problem:**  
LogEntry (and optionally file logs) grow unbounded with request volume. No automatic pruning or archival is configured in code (clean_old_logs_task exists but targets file logs; LogEntry table is not mentioned). Large tables slow queries and increase backup size.

**Severity:** MEDIUM  

**Fix approach:**  
- Add a scheduled task (or Celery Beat job) to archive or delete old LogEntry rows (e.g. older than 90 days), or move them to an archive table/partition.  
- Apply retention policy to CashfreeAPILog and APIKeyUsageLog if they grow large.  
- Document retention in runbooks and ensure clean_old_logs (file) runs on a schedule.

---

### 4.4 Rate Limit State in Redis – No Eviction Policy Documented

**Why it is a problem:**  
Throttling uses Redis keys per key/service/partner with TTL (60s, 3600s). Under many API keys and high request rate, key count and memory can grow. If Redis evicts keys under memory pressure, rate limiting becomes inconsistent (under or over limiting).

**Severity:** LOW  

**Fix approach:**  
- Document Redis memory and eviction policy (e.g. volatile-lru for throttle keys).  
- Use a key prefix (e.g. `ratelimit:`) and set TTL on all throttle keys so they expire; avoid unbounded growth.  
- Optionally cap the number of active API keys or throttle keys per partner.

---

## 5. Operational Risks

### 5.1 Sentry Disabled

**Why it is a problem:**  
Sentry is disabled in settings due to dependency conflict with cashfree_pg. Production errors and performance issues are not aggregated or alerted; failures may only appear in logs or user reports.

**Severity:** HIGH  

**Fix approach:**  
- Resolve dependency conflict (e.g. upgrade cashfree_pg or pin a compatible sentry-sdk version) and re-enable Sentry in production.  
- Or use an alternative (e.g. another error-tracking service, or structured logs + log-based alerts) so critical errors and high 5xx rate trigger alerts.

---

### 5.2 No Structured Health Checks for Celery or Redis

**Why it is a problem:**  
Health endpoint returns “API is healthy” but does not check DB, Redis, or Celery worker availability. A degraded Redis or Celery can cause timeouts and failed tasks while the API still returns 200.

**Severity:** MEDIUM  

**Fix approach:**  
- Add a dedicated health URL (e.g. `/api/v1/health/` or `/health/ready/`) that: pings DB (e.g. one simple query), pings Redis (cache.get/set), and optionally checks Celery (e.g. inspect ping or task result backend). Return 503 if any dependency fails.  
- Use this URL for load balancer or orchestrator readiness/liveness so traffic is stopped when dependencies are down.

---

### 5.3 Partner Charge Failure Not Surfaced to Partner or Admin

**Why it is a problem:**  
When `charge_partner_for_service` returns (None, False) (e.g. insufficient balance), the API v2 voucher (or KYC) view may still return success with voucher/verification data. Partner is not told that the charge failed; they may assume the full flow succeeded. Admin has no built-in view of “failed charges” or “unbilled usage”.

**Severity:** MEDIUM  

**Fix approach:**  
- If charge fails after service delivery: return 402 or a specific error code and message (e.g. “Service performed but wallet charge failed; please top up”) and do not return voucher/verification details until charge succeeds, or return them with a “billing_failed” flag.  
- Persist “failed_charge” or “pending_billing” records and add an admin view (or report) listing them so operations can follow up (top-up, retry, or manual adjustment).

---

### 5.4 Celery Beat Schedule Not in Codebase

**Why it is a problem:**  
Periodic tasks (clean_old_logs, cleanup_expired_voucher_otps, unblock_pin_locked_vouchers) are not registered in CELERY_BEAT_SCHEDULE. Operators must configure Beat externally or run cron; schedule can drift or be forgotten in new environments.

**Severity:** MEDIUM  

**Fix approach:**  
- Add CELERY_BEAT_SCHEDULE in Django settings (or in core/celery.py) for clean_old_logs, cleanup_expired_voucher_otps, unblock_pin_locked_vouchers with explicit intervals (e.g. daily, every 10 minutes).  
- Document in deployment runbook that Beat must be running for these schedules.

---

### 5.5 Bulk Batch Failure – Only Logged; No Admin Alert

**Why it is a problem:**  
When bulk voucher processing fails (exception or max retries), batch status is set to FAILED and error_log is written. There is no automatic notification to admin (email, Slack, or dashboard alert). Large batches can fail overnight and be noticed only when someone checks the batch list.

**Severity:** LOW  

**Fix approach:**  
- On batch status transition to FAILED, trigger an alert: e.g. send email to configured admin list, or post to a webhook/Slack, or create a “high priority” ticket.  
- Optionally add a simple “recent failures” widget on admin dashboard or a daily digest of failed batches.

---

## 6. Hardcoded Logic & Tech Debt

### 6.1 Payment Gateway Placeholder

**Why it is a problem:**  
Payment initiate/status/refund are stubs. See 1.1.

**Severity:** HIGH  

**Fix approach:**  
- Implement real gateway integration and remove placeholder responses.

---

### 6.2 Rate Limit Defaults Hardcoded in Throttling Class

**Why it is a problem:**  
Default requests_per_minute and requests_per_hour are hardcoded in api/v2/throttling.py (e.g. 100/1000 for key, 500–20000 per service). Changing them requires code change and deploy; different environments (e.g. staging vs production) cannot tune without code.

**Severity:** LOW  

**Fix approach:**  
- Move default limits to Django settings or config (e.g. core/config.py or env). Use settings in throttle classes so production can override via env (e.g. API_RATE_LIMIT_VOUCHER_PER_MIN=200).

---

### 6.3 Vendor Selection (BBPS, etc.) by Param or Config

**Why it is a problem:**  
BBPS vendor (Mobikwik vs Euronet) is chosen by request param or config. If a partner sends the wrong vendor or config is mis-set, wrong vendor is called; failure modes and support burden increase. No single source of truth for “which vendor for which partner/service”.

**Severity:** LOW  

**Fix approach:**  
- Document clearly how vendor is chosen (param vs config vs partner-level override).  
- Consider storing default BBPS (and similar) vendor per service or per partner in DB so it can be changed without code deploy and audited.

---

### 6.4 Magic Numbers for File Size and PIN Retry

**Why it is a problem:**  
File size limits (e.g. 10MB bulk, 5MB KYC in UI) and PIN retry count (e.g. 3) are hardcoded in multiple places. Changing them requires code search and multiple edits; risk of inconsistency (e.g. form says 5MB but backend allows 10MB).

**Severity:** LOW  

**Fix approach:**  
- Centralize in settings or config: e.g. BULK_UPLOAD_MAX_MB, KYC_UPLOAD_MAX_MB, VOUCHER_PIN_MAX_RETRIES. Use these in validators, serializers, and templates (if rendered server-side). Document in TECHNICAL_DOCUMENTATION and .env.example.

---

### 6.5 Wallet Model – status vs is_active

**Why it is a problem:**  
WalletService uses `is_active=True` in get_or_create_wallet defaults; Wallet model defines status choices (active, frozen, closed). If the model uses a `status` field instead of `is_active`, the service defaults may be wrong or out of sync.

**Severity:** LOW (verify model field names)

**Fix approach:**  
- Confirm Wallet model field (status vs is_active) and align WalletService and PartnerAccountingService with the same field and values. Use a single source of truth (model) for “active” wallet.

---

## Summary Table

| #   | Issue                                      | Severity |
|-----|--------------------------------------------|----------|
| 1.1 | Payment initiate placeholder               | HIGH     |
| 1.2 | No rollback when partner charge fails      | MEDIUM   |
| 1.3 | KYC upload no server-side size/type        | MEDIUM   |
| 1.4 | Partner wallet not auto-created             | MEDIUM   |
| 1.5 | Fallback to full amount when no pricing    | LOW      |
| 2.1 | No idempotency keys on financial APIs      | HIGH     |
| 2.2 | Voucher redeem duplicate only if ref sent   | HIGH     |
| 2.3 | Partner wallet debit not atomic            | HIGH     |
| 2.4 | Voucher redeem without row lock            | HIGH     |
| 2.5 | Public endpoints abuse control              | LOW      |
| 2.6 | Rate limits high and not risk-tuned        | MEDIUM   |
| 3.1 | Partner wallet update not atomic           | HIGH     |
| 3.2 | WalletTransaction model/service mismatch   | HIGH     |
| 3.3 | Bulk task progress vs retry                | MEDIUM   |
| 3.4 | Voucher redeem no select_for_update       | HIGH     |
| 4.1 | Every request enqueues log task            | MEDIUM   |
| 4.2 | Bulk processing single task                | MEDIUM   |
| 4.3 | LogEntry/DB log growth                     | MEDIUM   |
| 4.4 | Redis rate-limit eviction                  | LOW      |
| 5.1 | Sentry disabled                            | HIGH     |
| 5.2 | Health check not dependency-aware          | MEDIUM   |
| 5.3 | Partner charge failure not surfaced        | MEDIUM   |
| 5.4 | Celery Beat schedule not in code           | MEDIUM   |
| 5.5 | Bulk failure no admin alert                | LOW      |
| 6.1 | Payment placeholder (tech debt)            | HIGH     |
| 6.2 | Rate limits hardcoded                      | LOW      |
| 6.3 | Vendor selection logic                     | LOW      |
| 6.4 | File size / PIN retry magic numbers       | LOW      |
| 6.5 | Wallet status vs is_active                 | LOW      |

---

## Re-review: Financial Safety Guarantees (Post-Fix)

### Confirmed

| Guarantee | Status | Evidence |
|-----------|--------|----------|
| **Double voucher redemption impossible under concurrency** | **Confirmed** | `VoucherService.redeem_voucher_pin` and `redeem_voucher_otp` both run inside `transaction.atomic()` and re-fetch the voucher with `GiftVoucher.objects.select_for_update().get(id=voucher.id)`. Status and balance are re-validated after the lock (BLOCKED, EXPIRED, FULLY_REDEEMED, `amount > current_balance`). Concurrent requests serialize on the voucher row; the second sees updated status/balance and fails. |
| **Partner wallet balance cannot go negative due to race conditions** | **Confirmed** | `charge_partner_for_service` uses a single `transaction.atomic()` with wallet `select_for_update()`. Balance check after lock; debit, `WalletTransaction`, and REVENUE (create PENDING then COMPLETED when reference_id set) in one block. DB unique (partner, reference_id) for REVENUE prevents double-debit by reference_id; on IntegrityError return existing without debiting. Concurrent charges serialize; insufficient balance returns `(None, False)`. |
| **Duplicate API calls with same idempotency key return same result** | **Confirmed** | `IdempotencyMixin` on voucher issue (single/bulk), redeem PIN, and redeem OTP: when `X-Idempotency-Key` or `idempotency_key` is present, `get_cached_response(scope, key)` returns stored `(status, body)` within 24h TTL; replay returns that response. First request runs the view, then `store_response` with `IdempotencyRecord.get_or_create`; unique constraint `(scope, idempotency_key)` ensures one stored response per key. If two requests run concurrently, the second’s `store_response` hits `IntegrityError`, then `get_cached_response` returns the first’s stored response, so the client always receives the same response. |
| **Partial wallet debits cannot occur** | **Confirmed** | Partner path: one `transaction.atomic()` in `charge_partner_for_service` contains wallet lock, balance check, debit, `WalletTransaction` create, and `record_transaction`. Any failure rolls back the whole block. General `WalletService.deduct_funds`: one `transaction.atomic()` with `select_for_update()`, balance check, debit, and `WalletTransaction.objects.create`; no intermediate commit. |

### Remaining Risks

1. **Idempotency: business operation may run twice under concurrency**  
   Two requests with the same idempotency key can both miss the cache and both run the view (e.g. redeem). The first stores the response; the second fails to store and returns the first’s stored response. Clients see the same response, but the underlying operation (e.g. redemption) may have executed twice. To enforce “execute at most once” at the business layer, the first writer would need to reserve the idempotency key (e.g. insert a “pending” record) before running the view, or run the money-moving logic inside a single atomic step keyed by idempotency.

2. **Partner charge by `reference_id`: double charge under concurrency**  
   The “already charged for this `reference_id`” check in `charge_partner_for_service` is *outside* the `transaction.atomic()` block. Two concurrent requests with the same `reference_id` can both see no existing REVENUE row, then both enter the atomic block. The first debits and creates the REVENUE transaction; the second, after acquiring the lock, may still have sufficient balance (e.g. two small charges) and debit again, creating a second REVENUE with the same `reference_id`. So idempotency by `reference_id` is not guaranteed under concurrency. **Mitigation:** Move the “existing REVENUE for (partner, reference_id)” check inside the atomic block after locking the wallet, or add a DB unique constraint on `(partner, reference_id)` for REVENUE (or equivalent) and handle `IntegrityError` by returning the existing transaction.

3. **Celery Beat schedule**  
   Periodic tasks (e.g. log cleanup, voucher OTP cleanup, PIN unlock) are not defined in code; they depend on external Beat configuration or manual runs.

4. **Sentry disabled**  
   Production error monitoring remains off due to dependency/configuration constraints.

5. **Payment initiate placeholder**  
   `/api/v2/payments/initiate/` still returns placeholder data; not suitable for production use.

6. **KYC / partner charge failure handling**  
   Existing MEDIUM items (e.g. no rollback when partner charge fails, partner charge failure not surfaced to caller) remain as documented in the summary table.

---

*End of self-audit report. Prioritise HIGH severity items (financial integrity, security, and operations) before MEDIUM and LOW.*
