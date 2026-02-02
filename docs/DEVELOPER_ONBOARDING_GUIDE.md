# Payswap – Complete Developer Onboarding Guide

This guide helps new developers understand how the system really works, where mistakes are dangerous, and how to safely add features. It is based on the existing code, Technical Documentation, Self-Audit, and Financial Safety fixes.

**Assume:** You know Django but not this project. Read this before touching money-moving or partner-charging code.

---

## 1. Mental Model of the System

### What kind of system this is

- **Fintech, money-moving, API-first.** Payswap is a backend platform that:
  - Moves or records **money** (voucher issuance, redemption, partner wallet debits, settlements).
  - Exposes **REST APIs** for external partners (API key auth) and internal staff (session auth).
  - Integrates with **vendors** (SMS, KYC, payments, BBPS, AEPS, DMT).

- **Two main audiences:** Internal portal (Django templates, dashboards, tickets, logs) and **API v2** (partners calling voucher, KYC, payment, SMS, BBPS, AEPS, DMT). Money flows often go: partner calls API → we perform action (e.g. issue voucher) → we **debit the partner’s wallet** for that service.

- **Async work:** Celery runs bulk voucher processing, SMS, email, OTP, logging, and cleanup. Some of this touches the same DB rows (e.g. bulk batch progress) and must stay consistent.

### Invariants that MUST NEVER be broken

1. **No double-spend.** A voucher must not be redeemed twice; a partner must not be debited twice for the same logical operation (same reference).
2. **No negative partner wallet.** Balance checks must happen **after** locking the wallet row; debits must be inside a single atomic block with the balance check.
3. **No partial debits.** Wallet debit + creation of the related transaction record(s) must succeed or fail together (one atomic block).
4. **Idempotency for money-moving APIs.** Duplicate requests with the same idempotency key must not run business logic twice; at most one request executes, others get the stored response or 409.

### Why correctness > speed here

- **Money and compliance.** Double redemption, double charge, or negative balance cause financial loss, partner disputes, and audit failure. A slow but correct API is acceptable; a fast but wrong one is not.
- **Concurrency is real.** Retries, double-clicks, and parallel requests happen. The design uses **database uniqueness** and **row locking** so that under concurrency only one request “wins” for a given key or reference.

---

## 2. High-Risk vs Low-Risk Areas

### 🔴 Financial-critical (DO NOT TOUCH casually)

| Area | Why it is risky |
|------|------------------|
| **Idempotency (reserve / complete / fail)** | If you change when we reserve or complete, two requests can both run business logic (double issue, double redeem, double charge). |
| **Partner wallet debit (`charge_partner_for_service`)** | The flow reserves reference_id with a DB unique constraint, then debits inside one atomic block. Removing the constraint, moving the “existing charge” check outside the atomic block, or splitting debit and transaction creation can cause double-debit or negative balance. |
| **Voucher redemption (PIN and OTP)** | Uses row lock on the voucher and re-checks status/balance inside the atomic block. Skipping the lock or the re-check allows double redemption. |
| **Wallet debit in `WalletService.deduct_funds`** | Lock + balance check + debit + WalletTransaction create are in one atomic block. Splitting them can cause partial debits or negative balance. |
| **`IdempotencyRecord` model and unique (scope, idempotency_key)** | The whole “execute at most once” guarantee depends on this. Do not relax uniqueness or change status flow without a full concurrency review. |
| **`ResellerPartnerTransaction` unique (partner, reference_id) for REVENUE** | This is the DB guarantee that the same reference_id is not charged twice. Do not remove or weaken this constraint. |

**Rule:** Any change in these areas must preserve: one atomic block for debit + related records, lock-before-check for balance/voucher state, and idempotency reserve-before-execute.

---

### 🟡 Business logic (change with care)

| Area | Why it needs care |
|------|--------------------|
| **Voucher issuance (single and bulk)** | Creates vouchers and then charges the partner. If you change pricing, brand/client logic, or email/SMS triggers, ensure partner charging still receives a valid reference_id and that failures are visible (no silent swallow). |
| **KYC flows and partner charging** | Same idea: we perform verification then charge. Charging failure is currently logged but may not always fail the API response; be explicit about when to return 402 or 500. |
| **Pricing and commission** | `ResellerPartnerPricing`, `calculate_price`, `calculate_commission`, and `_ensure_commission_for_revenue` affect how much we charge and credit. Wrong formulas = wrong money. |
| **Bulk voucher batch processing** | Celery task updates batch progress and creates vouchers. Progress and status must stay consistent; use the existing locking (e.g. batch row lock) when touching progress. |
| **Voucher PIN/OTP validation** | Lockout rules, OTP expiry, and retry counts affect security and UX. Change only with clear rules and tests. |

**Rule:** Test with realistic data; ensure partner is charged the correct amount and that failures are observable (logs, status, or response).

---

### 🟢 Safe / non-critical

| Area | Why it is relatively safe |
|------|----------------------------|
| **Portal UI (templates, static, dashboards)** | No direct money movement; auth and permissions still matter but mistakes are less likely to cause double-spend. |
| **Read-only APIs** (e.g. balance, list batches, health) | No writes to wallet or voucher state; still respect auth and rate limits. |
| **Logging and audit** | Adding or changing log fields does not change money flow; avoid logging sensitive data. |
| **SMS/email content and templates** | Content changes do not affect idempotency or locking; delivery failures are retried by tasks. |
| **Admin list/filter views** | Display and filters; no financial invariants unless you add actions that debit or change status. |
| **Vendor API wrappers (non-money)** | E.g. fetching operators or bill fetch; idempotency and locking live in our layer, not in the vendor call. |

**Rule:** You still need tests and review, but the risk of double-spend or negative balance is low.

---

## 3. Money Flow Explained (Step-by-Step)

### Voucher issue flow (single, API v2)

1. Partner sends POST with brand, amount, email, and optionally an **idempotency key** (header or body).
2. **Idempotency:** We try to **reserve** the key (INSERT a row with status PENDING). Only if we create that row do we continue; otherwise we return stored response (if COMPLETED) or 409 (if PENDING/FAILED).
3. We validate brand and amount, then create the voucher (code, PIN, balance, status) and an initial transaction record in the DB.
4. We **charge the partner**: look up pricing, then call `charge_partner_for_service` with a **reference_id** (e.g. voucher reference_number). That flow reserves reference_id (create REVENUE PENDING), then in one atomic block locks the wallet, checks balance, debits, creates WalletTransaction, and marks REVENUE COMPLETED. Commission is created after that block.
5. We **complete idempotency** (store response and set status COMPLETED). If any step fails, we **fail idempotency** (set FAILED) and re-raise.

So: **one idempotency key → at most one voucher creation.** **One reference_id → at most one wallet debit.**

---

### Voucher redeem flow (PIN or OTP, API v2)

1. Partner sends redeem request with voucher code, PIN (or OTP), and amount, plus optional idempotency key.
2. **Idempotency:** Same as above – reserve key; only the request that reserves runs the rest.
3. We validate voucher, PIN/OTP, and amount **outside** the critical section.
4. **Critical section:** We open a single atomic block, **re-fetch the voucher row with a row lock** (so no other request can redeem it at the same time), then **re-check** status (not blocked/expired/fully redeemed) and balance (amount ≤ current balance). Only then do we reduce balance, update status, and create the redemption transaction.
5. We complete or fail idempotency.

So: **two concurrent redeem requests** for the same voucher **serialize** on the locked row; the second sees updated balance/status and fails. **One idempotency key → at most one redemption.**

---

### Partner wallet debit flow (with reference_id)

1. Caller (e.g. voucher issue or KYC) calls `charge_partner_for_service(partner, service, amount, reference_id=..., ...)`.
2. **When reference_id is set:** Inside one atomic block we **try to create** a REVENUE row with status PENDING. The DB has a unique constraint on (partner, reference_id) for REVENUE. So either we create (and “reserve” the reference_id) or we get IntegrityError.
3. **If IntegrityError:** We load the existing REVENUE row and **return it without touching the wallet.** So the same reference_id is never debited twice.
4. **If we created PENDING:** We lock the partner’s wallet row, check balance ≥ amount. If insufficient, we mark the REVENUE row as FAILED and return (no debit). If sufficient, we debit the wallet, create a WalletTransaction, and set the REVENUE row to COMPLETED. All in the **same** atomic block.
5. After the block we create commission (separate credit) if pricing says so.

So: **wallet balance changes only once per (partner, reference_id)** and **exactly one REVENUE row** exists for that pair.

---

### Idempotency + locking strategy (why it exists)

- **Idempotency** ensures that **duplicate HTTP requests** (same key) do not run the **business logic** twice. We **reserve** the key at the **start** (INSERT PENDING). Only the request that inserts runs the view; others get stored response or 409. So we get “execute at most once” per key, not just “return same response after the fact.”
- **Locking** ensures that **concurrent requests** that touch the **same row** (same voucher, same wallet) do not both read the same state and both proceed. We use **row-level lock** (select_for_update) so that the second request waits, then sees the updated state and (for redeem) fails the re-check; for charge, the second request hits the unique constraint and returns the existing transaction without debiting.

So: **idempotency** = per-request key; **locking** = per-row serialization; **unique constraint** = per (partner, reference_id) for REVENUE.

---

### Why select_for_update and atomic blocks exist

- **Without a lock:** Two requests can both read “balance = 100” and both debit 60, so balance becomes -20 or only one debit is recorded. Or two redeems both read “balance = 50” and both redeem 50.
- **With select_for_update:** The second request **blocks** until the first commits. Then it reads the **new** balance or status and either fails the check (insufficient balance, voucher already redeemed) or proceeds if the state still allows it (e.g. two different reference_ids).
- **Atomic block:** So that “debit wallet” and “create WalletTransaction (and REVENUE)” are one unit. If anything fails, everything rolls back; we never have a debit without a transaction record or vice versa.

---

## 4. Idempotency Rules (Very Important)

### What idempotency keys are

- A **client-chosen string** (e.g. UUID) sent per request so we can recognize “this is the same logical request as before.”
- Accepted via **header** (`X-Idempotency-Key`) or **body** (`idempotency_key`).
- **Scope** = partner + endpoint (e.g. partner_123:v2:voucher_issue). Same key in a different scope is a different idempotency slot.

### Where they are REQUIRED

- **Strong idempotency (reserve at start)** is applied to:
  - Voucher issue (single)
  - Voucher issue (bulk)
  - Voucher redeem (PIN)
  - Voucher redeem (OTP)
- For these, when the client sends an idempotency key, **only one request** runs business logic; others get stored response or 409. **Best practice:** Require idempotency keys for these in production (document and enforce in partner agreements).

### What happens if they are misused

- **Reusing a key for a different operation:** We store response by (scope, key). If the client reuses the key for a different voucher or amount, the second request gets the **first request’s** stored response (wrong). So: **one key = one logical operation.** Client must generate a new key per distinct operation.
- **Sending no key:** Request is processed normally; duplicate submissions (retries, double-clicks) can cause double issue, double redeem, or double charge. So for money-moving APIs we **should** require the key in production.
- **Same key, concurrent:** Only one request creates the PENDING row; others get replay or 409. Correct.

### Common mistakes developers make with idempotency

1. **Caching response after execution.** That only guarantees “same response” on replay; it does **not** guarantee “execute once.” We use **reserve-before-execute** so only one request runs.
2. **Checking “have we seen this key?” outside a transaction.** Two requests can both see “no” and both run. We use **INSERT** (unique constraint) inside a transaction so only one can succeed.
3. **Using one key for multiple operations.** Key must be unique per logical operation (e.g. one key per voucher issue, one per redeem).
4. **Treating 409 as a generic error.** 409 means “this key is in use or previously failed.” Client should not retry with the **same** key; use a new key for a new attempt.

---

## 5. Database Locking & Transactions

### Where select_for_update is used

- **Partner wallet:** In `charge_partner_for_service` we lock the partner’s wallet row before checking balance and debiting. So concurrent charges on the same partner serialize.
- **Voucher row:** In PIN and OTP redeem we re-fetch the voucher with select_for_update inside the atomic block and re-validate status/balance. So concurrent redeems on the same voucher serialize.
- **User wallet:** In `WalletService.add_funds` and `deduct_funds` we lock the wallet row before updating balance and creating WalletTransaction.
- **Bulk batch:** When processing a bulk voucher batch, the batch row can be locked so progress updates are consistent.

### Why wallet and voucher rows must be locked

- **Wallet:** Balance is read, then updated. Without a lock, two requests can both read the same balance and both debit, causing negative balance or lost updates. The lock forces the second to wait and then see the new balance.
- **Voucher:** Balance and status are read, then updated. Without a lock, two redeems can both see “balance 100” and both redeem 100 (double-spend). The lock forces the second to wait and then see “balance 0” or “fully redeemed” and fail.

### What can break if a dev removes atomic blocks

- **Partial debit:** Wallet balance decreased but no WalletTransaction or REVENUE row (or vice versa). Ledger inconsistent, reconciliation fails.
- **Double debit:** Two requests both pass the balance check, both debit; balance goes negative or we create two REVENUE rows for the same reference_id (the unique constraint prevents the second if we keep it; if someone removes the atomic block and the “create first” pattern, double debit can return).
- **Double redemption:** Two requests both see “balance 50,” both redeem 50; voucher balance goes negative or two redemption transactions for same voucher.

So: **do not remove or split the atomic blocks** that wrap debit + transaction creation and voucher redeem. Do not remove select_for_update from wallet or voucher paths.

---

## 6. How to Safely Add a New API

### Checklist before adding any API

- [ ] Does this API **move or record money** (debit wallet, create voucher, redeem, charge partner)? If yes, it must participate in **idempotency** and **locking** as below.
- [ ] Does it **charge the partner**? If yes, use `charge_partner_for_service` with a **reference_id** (e.g. order_id or our own reference); do not implement your own debit logic.
- [ ] Is it **idempotent by design**? If it is money-moving, accept `X-Idempotency-Key` (or body) and use the existing IdempotencyMixin (reserve → execute → complete/fail).
- [ ] Are errors **visible**? Do not swallow partner charge failures; log and optionally return 402 or 500 so the caller knows.

### Questions a developer must ask themselves

1. “If the client sends this request twice (same idempotency key), do we run the operation twice?” If yes, add strong idempotency (reserve at start).
2. “If two requests run at once for the same resource (same voucher, same partner reference), can both succeed?” If yes, add locking and/or unique constraint.
3. “If we debit the wallet but then fail before creating the transaction record, do we leave the ledger inconsistent?” If yes, put debit and record creation in one atomic block.

### Example: adding a new “chargeable service”

1. Define the **service** (e.g. in Service model) and **partner pricing** (ResellerPartnerPricing).
2. In the API view, after performing the service (e.g. calling an external API), call `PartnerAccountingService.charge_partner_for_service(partner, service, amount, reference_id=..., ...)`. Use a **stable reference_id** (e.g. external order_id or our own unique id) so the same operation is not charged twice.
3. If the API is money-moving, add **IdempotencyMixin** and set `idempotency_scope_suffix` (e.g. `v2:my_new_service`). Ensure the view runs only after reserve (mixin does this).
4. Do **not** implement your own “check if we already charged” outside the atomic block; the service uses the DB unique constraint and create-first pattern. Do **not** debit the wallet yourself; use `charge_partner_for_service`.

---

## 7. How to Safely Add a New Vendor Integration

### Where vendor code should live

- **Service layer:** `portal/services/` (e.g. a new `xyz_service.py` that calls the vendor).
- **Vendor-specific client:** `portal/services/vendors/` (e.g. `portal/services/vendors/xyz.py`) for HTTP/client logic, credentials, and response parsing. The service layer then uses this client and maps results to our models.

### How failures should be handled

- **Network/timeout:** Retry with backoff where the vendor allows it; do not retry blindly for money-moving calls unless the operation is idempotent on the vendor side.
- **4xx from vendor:** Do not retry; return a clear error to the caller (e.g. invalid params, rejected).
- **5xx / unknown:** Log, optionally retry once; if we already created a local record (e.g. voucher or REVENUE PENDING), decide whether to mark failed or leave for manual review. Do not leave partner debited without a corresponding successful operation if that violates the business rule.

### How retries, idempotency, and logging must work

- **Idempotency:** Our **API** is idempotent by key. If the view calls the vendor and the vendor fails, we **fail_idempotency** so the client can retry with the **same** key and we will not run the view again (they get 409) or we need a defined “retry same key” policy. Today we fail idempotency on exception, so the same key returns 409 on replay. For “retry same key,” we would need a documented flow (e.g. allow retry for FAILED keys within a window).
- **Retries:** Celery tasks often have max_retries. For tasks that call vendors, ensure that retrying the task does not double-charge or double-issue; use the same reference_id or batch id so our side stays idempotent.
- **Logging:** Log vendor request/response (sanitized: no full card or secrets) and our decision (success/fail/retry). Use the existing logging helpers and categories so operations can trace flows.

---

## 8. Common Anti-Patterns (DO NOT DO THIS)

1. **Read-then-write without lock**  
   Example: read wallet balance, then in a later line debit. Another request can run in between. ✅ **MUST** lock the row (select_for_update) then read then write inside one atomic block.

2. **Cache-only idempotency**  
   Example: “if key in cache, return cached response; else run view and put response in cache.” Two requests can both miss cache and both run. ✅ **MUST** use reserve-at-start (INSERT PENDING) so only one request can “own” the key.

3. **Side effects outside atomic blocks**  
   Example: debit wallet inside atomic, then send email and create WalletTransaction outside. If email fails, we have debited but no record. ✅ **MUST** put debit and all related DB writes (WalletTransaction, REVENUE) in one atomic block; side effects (email, commission credit) can be after.

4. **Silent failure of partner charges**  
   Example: catch exception from `charge_partner_for_service` and return 200 anyway. Partner got service but we did not charge. ✅ **MUST** log and at least return 402 or 500 so the caller and ops know; prefer failing the request or marking “unbilled” for follow-up.

5. **Checking “already charged?” outside the atomic block**  
   Two requests can both see “not charged” and both debit. ✅ **MUST** use DB unique constraint + create-first (or check inside the same atomic block after lock).

6. **Removing or weakening unique constraints**  
   The unique (scope, idempotency_key) and unique (partner, reference_id) for REVENUE exist so that the DB enforces “at most one.” Removing them to “simplify” or allow “flexibility” breaks the guarantee. ✅ **DO NOT** remove these constraints.

7. **One idempotency key for multiple operations**  
   Example: same key for “issue 10 vouchers” and then “issue 10 more.” Replay would return the first response for both. ✅ **MUST** use one key per distinct logical operation.

---

## 9. Testing Expectations

### What must be tested manually

- **Voucher issue then redeem:** Issue a voucher, redeem once (full or partial), try to redeem again (must fail). Check balance and status.
- **Idempotency:** Same request (same key) twice; second must return same response without creating a second voucher or second debit. Concurrent: two requests with same key; one must succeed, one must get stored response or 409.
- **Partner charge:** Same reference_id twice; second must return existing transaction and wallet balance must change only once. Concurrent: two requests with same reference_id; one debit, one “already exists.”

### What must be tested with concurrency in mind

- **Double redemption:** Two parallel redeem requests for the same voucher; only one must succeed, the other must get insufficient balance or already redeemed.
- **Double charge:** Two parallel charge_partner_for_service calls with same (partner, reference_id); only one debit, one REVENUE COMPLETED, the other returns existing.
- **Idempotency reserve:** Two parallel requests with same idempotency key; only one must run the view; the other gets stored response or 409.

### What is acceptable to mock vs not mock

- **Mock:** External vendor HTTP (KYC, SMS, payment gateway) so tests are fast and deterministic. Still test that we call the right endpoint with the right params and handle success/failure as expected.
- **Do not mock:** DB uniqueness and locking. Use a real DB (e.g. SQLite or PostgreSQL in CI) so that unique constraints and select_for_update actually run. Otherwise you can miss double-insert or double-debit bugs.

---

## 10. How This System Can Fail (And How to Notice Early)

### Symptoms of race conditions

- **Negative wallet balance** or **two REVENUE rows for same reference_id** (if constraint were removed or bypassed).  
- **Voucher balance negative** or **two redemption transactions** for the same voucher.  
- **“Insufficient balance”** even though the UI shows enough (another request debited between read and write).

**Where to look:** Any path that **updates balance or status** without select_for_update in an atomic block; any “check then create” without a unique constraint.

---

### Symptoms of stuck idempotency

- **409 on every retry** with the same key even though the first request failed (we marked FAILED; client keeps retrying same key).  
- **PENDING rows** in IdempotencyRecord that never become COMPLETED or FAILED (request crashed after reserve, before complete/fail).

**Where to look:** IdempotencyRecord table (status, created_at). Document for clients: “Use a new key for a new attempt after 409 or server error.” Consider a periodic job to mark old PENDING as FAILED and/or TTL for replay.

---

### Symptoms of wallet mismatch

- **Partner balance in UI** does not match sum of WalletTransaction rows.  
- **REVENUE rows** exist but no corresponding WalletTransaction debit (or vice versa).

**Where to look:** charge_partner_for_service and any code that writes to Wallet or WalletTransaction. Ensure every debit is in one atomic block with the corresponding WalletTransaction (and REVENUE) create.

---

### Where to look first when something feels “off”

1. **Recent changes** to: idempotency (reserve/complete/fail), charge_partner_for_service, voucher redeem, WalletService.deduct_funds.  
2. **Logs:** Partner charge failures, IntegrityError, “Insufficient balance,” “already redeemed.”  
3. **DB:** IdempotencyRecord (stuck PENDING/FAILED), ResellerPartnerTransaction (duplicate reference_id if constraint is missing), WalletTransaction vs Wallet.balance for a partner.  
4. **Concurrency:** Reproduce with two parallel requests (same key or same reference_id) and check that only one executes and balance/state are correct.

---

*End of Developer Onboarding Guide. Use together with [TECHNICAL_DOCUMENTATION.md](./TECHNICAL_DOCUMENTATION.md), [SELF_AUDIT_REPORT.md](./SELF_AUDIT_REPORT.md), and [FINANCIAL_SAFETY_GUARANTEES.md](./FINANCIAL_SAFETY_GUARANTEES.md).*
