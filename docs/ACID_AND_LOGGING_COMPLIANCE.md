# Payswap / ParkPe – ACID & Logging Compliance

**All financial operations are ACID-compliant, transaction-based, and file-system logged.**

This document summarizes how the codebase enforces correctness, durability, and audit safety. See [ADMIN_CONTROL_AND_APPROVAL_MATRIX.md](./ADMIN_CONTROL_AND_APPROVAL_MATRIX.md) for risk levels and approval rules.

---

## 1. ACID Requirements (Mandatory)

### Atomicity
- Wallet balance update + `WalletTransaction` record + audit history (django-simple-history) succeed or fail **together** inside `transaction.atomic()`.
- No partial commits. No side effects outside the atomic block for financial writes.
- Manual partner wallet credit/debit, settlement execution, and voucher status override run in a single atomic block with row locks.

### Consistency
- **Wallet:** `CheckConstraint` enforces `balance >= 0` (DB-level). Service layer checks balance after `select_for_update()` before debit.
- **Voucher:** `CheckConstraint` enforces `current_balance >= 0` and `original_amount >= 0`. Voucher cannot be redeemed if status is BLOCKED / EXPIRED / FULLY_REDEEMED; checks are done **after** row lock.
- **Same reference_id:** At most one REVENUE per (partner, reference_id) via `UniqueConstraint` on `ResellerPartnerTransaction`.
- **Idempotency:** Same idempotency key executes at most once (reserve-before-execute; IdempotencyRecord is not audited by simple_history).

### Isolation
- **Wallet:** All balance mutations use `Wallet.objects.select_for_update().get(id=...)` inside `transaction.atomic()`.
- **Voucher:** Redeem and status override use `GiftVoucher.objects.select_for_update().get(id=...)` inside `transaction.atomic()`.
- **Settlement:** `process_settlement` uses `ResellerPartnerSettlement.objects.select_for_update().get(id=...)` and validates status is PENDING before updating.
- Balance/status checks happen **after** the row lock; concurrent requests serialize correctly.

### Durability
- All committed data persists after commit. No financial state stored only in cache or memory.
- Audit history (django-simple-history) is created in the **same** transaction as the model save/update/delete; rollback of the main write rolls back history.

---

## 2. Transaction Rules (Strict)

- All financial write operations are wrapped in `with transaction.atomic():`.
- For balance/state mutation: fetch row with `select_for_update()`, validate state **after** lock, apply update, create related transaction records, then commit once.
- **Prohibited:** Direct `.update()` on balance fields (we use instance save after lock), read-then-write without lock, cache-based money logic, signals that mutate financial data, manual DB writes outside the service layer.

---

## 3. Logging (File-System Only for Application Logs)

- Application logs are written to the **file system**, not database tables.
- Django `LOGGING` is configured with:
  - **logs/app.log** – general application logs (RotatingFileHandler, 10 MB × 5 backups).
  - **logs/finance.log** – wallet, voucher, settlement, partner accounting (logger `portal.finance`).
  - **logs/security.log** – auth, permission, admin actions (logger `portal.security`).
  - **logs/audit.log** – approval execution, overrides (logger `portal.audit`).
  - **logs/error.log** – uncaught exceptions / ERROR level (handler `error_file`).
- Logs must **never** affect DB transactions (logging is best-effort and must not fail the request).
- No secrets in logs (no PIN, OTP, API keys, tokens). Log reference_id, entity_id, user_id, action where applicable.
- Logging happens after successful commit (or is clearly marked as failed) so that we do not log success before commit.

---

## 4. Database Model Integrity

- **Foreign keys:** Wallet → User; WalletTransaction → Wallet; ResellerPartnerTransaction → ResellerPartner; GiftVoucher → GiftVoucherBrand, VoucherClient; ApprovalRequest → requested_by, approved_by. No raw IDs where a FK is applicable.
- **Constraints:**
  - `portal_wallet_balance_non_negative`: Wallet.balance >= 0.
  - `portal_giftvoucher_current_balance_non_negative`: GiftVoucher.current_balance >= 0.
  - `portal_giftvoucher_original_amount_non_negative`: GiftVoucher.original_amount >= 0.
  - `partner_revenue_reference_id_unique`: UniqueConstraint on (partner, reference_id) for REVENUE on ResellerPartnerTransaction.
- **on_delete:** PROTECT for financial entities where appropriate; CASCADE only where business rules allow.
- **Status fields:** Use model choices (e.g. Wallet.STATUS_CHOICES, GiftVoucher.STATUS_CHOICES).

---

## 5. Celery & Async Tasks

- Each Celery task that performs financial or state writes must open its own `transaction.atomic()` and use the same locking rules (`select_for_update()` for mutable rows).
- No partial writes on retry. Tasks must be idempotent by reference_id or batch_id.

---

## 6. Verification Checklist

- [x] No financial write exists outside atomic blocks (wallet, voucher, partner, settlement, approval execution).
- [x] `select_for_update()` is used for Wallet, GiftVoucher, ResellerPartnerSettlement in mutation paths.
- [x] Application logs are written to filesystem (app, finance, security, audit, error).
- [x] Models use ForeignKey and CheckConstraint/UniqueConstraint where specified.
- [x] Audit history (simple_history) rolls back when the main transaction fails.
- [x] Logging does not mutate or depend on DB state for the success path.

---

## 7. Areas Reviewed and Updated

- **WalletService:** add_funds, deduct_funds (atomic + select_for_update); freeze_wallet, unfreeze_wallet (atomic + select_for_update, use `status` not `is_active`); calculate_statistics (wallet.status == 'active').
- **PartnerAccountingService:** _update_partner_wallet (atomic + select_for_update; balance check on debit); process_settlement (atomic + select_for_update; validate PENDING); manual_partner_wallet_credit/debit already atomic with select_for_update.
- **ApprovalService:** _execute_voucher_status_override (atomic + select_for_update on voucher); approve_and_execute already uses transaction.atomic().
- **VoucherService:** redeem_voucher_pin / redeem_voucher_otp already use transaction.atomic() and select_for_update().
- **Settings:** LOGGING updated with file handlers for app, finance, security, audit, error.
- **Models:** CheckConstraints added for Wallet.balance and GiftVoucher.current_balance, original_amount.

---

*Correctness over performance. Money/state must never be inconsistent. No silent failures. Logs durable and tamper-resistant. Database is the source of truth.*
