# Financial Safety Changes – Summary

This document summarizes the changes made to address the four HIGH-severity issues from the self-audit report, without changing external API contracts unnecessarily.

---

## 1. Idempotency for Money-Moving APIs

**What was done**

- **Model**: Added `IdempotencyRecord` (scope, idempotency_key, response_http_status, response_body, created_at) with unique (scope, idempotency_key). TTL is enforced by filtering on `created_at` (24 hours).
- **Service**: `portal/services/idempotency_service.py` – `get_idempotency_key(request)` (from `X-Idempotency-Key` or body `idempotency_key`), `build_scope(partner_id, endpoint)`, `get_cached_response(scope, key)`, `store_response(...)`.
- **Mixin**: `api/v2/idempotency_mixin.py` – `IdempotencyMixin` with `idempotency_scope_suffix`. For POST requests with partner and idempotency key: if cached response exists (within 24h), return it; otherwise run the view, store response, return it. On concurrent duplicate key, `store_response` catches `IntegrityError` and returns False; mixin then fetches stored response and returns it.
- **Views**: Applied mixin and set `idempotency_scope_suffix` on:
  - `VoucherIssueView` → `v2:voucher_issue`
  - `BulkVoucherIssueView` → `v2:voucher_bulk_issue`
  - `VoucherRedeemPINView` → `v2:voucher_redeem_pin`
  - `VoucherRedeemOTPVerifyView` → `v2:voucher_redeem_otp`
- **Partner charging**: Idempotency by `reference_id` inside `charge_partner_for_service`: if a `ResellerPartnerTransaction` with same partner, `reference_id`, and type REVENUE already exists, return that transaction without debiting again.

**Backward compatibility**

- Idempotency is optional: if no `X-Idempotency-Key` or `idempotency_key` in body, request is processed as before.
- Response format is unchanged; replay returns the same JSON and status code.

---

## 2. Partner Wallet Debit Atomicity

**What was done**

- **`PartnerAccountingService.charge_partner_for_service`**:
  - Idempotency check by `reference_id` (see above) before any debit.
  - Entire debit flow wrapped in a single `transaction.atomic()` block.
  - Wallet is loaded with `Wallet.objects.select_for_update().get(id=partner.wallet_id)` so concurrent charges on the same partner serialize.
  - Balance is re-checked **after** acquiring the lock; if insufficient, return `(None, False)` and exit the atomic block (no partial write).
  - Creation of `WalletTransaction` and call to `record_transaction` (which creates `ResellerPartnerTransaction`) are both inside the same atomic block, so no partial writes.

**Inline comments**

- Comments in the method explain: idempotency by reference_id, single atomic block, lock to prevent races, re-check balance after lock.

---

## 3. Voucher Redemption Double-Spend Protection

**What was done**

- **`VoucherService.redeem_voucher_pin`** and **`redeem_voucher_otp`**:
  - All redemption logic (balance update + `GiftVoucherTransaction` creation) remains inside the existing `transaction.atomic()` block.
  - At the start of that block, the voucher is re-fetched with `GiftVoucher.objects.select_for_update().get(id=voucher.id)` so concurrent redemptions on the same voucher serialize on that row.
  - After acquiring the lock, status and balance are re-validated (BLOCKED, EXPIRED, FULLY_REDEEMED, insufficient balance); if any check fails, `ValueError` is raised and the transaction rolls back.
  - Balance update and transaction insert use the locked `voucher_locked` instance; no double-spend under concurrent requests.

**Inline comments**

- Comments explain: atomic block + row lock, re-validate after lock to prevent double-spend.

---

## 4. WalletTransaction Model vs Service Alignment

**What was done**

- **Model** (`portal/models.py`): On `WalletTransaction` added:
  - `description` (TextField, blank/null)
  - `reference_id` (CharField, blank/null, db_index=True)
  - `metadata` (JSONField, default=dict)
  - `performed_by` (ForeignKey to User, null=True)
- **Migration**: `portal/migrations/0023_idempotency_and_wallet_transaction_fields.py` adds these fields and the `IdempotencyRecord` model (see below).
- **WalletService**:
  - `get_or_create_wallet`: Defaults use `'status': 'active'` (Wallet model has `status`, not `is_active`).
  - `add_funds` / `deduct_funds`: Create `WalletTransaction` with `reference`, `description`, `reference_id`, `metadata`, `status='completed'`, `performed_by`; `transaction_type` set to lowercase `'credit'` / `'debit'` to match model choices.
- **PartnerAccountingService**: When creating `WalletTransaction` inside the charge flow, uses `reference` and `reference_id` (description text and idempotency/audit).

**Basic test**

- **`portal/tests/test_wallet_service.py`**: `TestWalletServiceDebit.test_deduct_funds_creates_transaction_and_updates_balance` – adds funds, then deducts; asserts balance change and that a `WalletTransaction` exists with `transaction_type='debit'`, `status='completed'`, `reference_id`, `description`, `performed_by`.  
- Note: Running this test with a fresh test DB can fail during migration setup because of an existing allauth migration that references `User.email` (our User keeps email on Profile). The migration `0023` and wallet debit logic have been run successfully on the main DB.

---

## Files Touched (no unrelated refactors)

- **Models**: `portal/models.py` – `WalletTransaction` new fields, `IdempotencyRecord` model.
- **Migration**: `portal/migrations/0023_idempotency_and_wallet_transaction_fields.py`.
- **Services**: `portal/services/partner_accounting_service.py`, `portal/services/wallet_service.py`, `portal/services/voucher_service.py`, `portal/services/idempotency_service.py` (new).
- **API v2**: `api/v2/idempotency_mixin.py` (new), `api/v2/voucher_views.py` (idempotency mixin, scope suffix, redeem views call `redeem_voucher_pin` / `redeem_voucher_otp` and map response).
- **Admin**: `portal/admin.py` – import and register `IdempotencyRecord`.
- **Test**: `portal/tests/test_wallet_service.py` (new).

**Not touched**

- UI templates, unrelated APIs, vendor integrations.

---

## Deploy / Run

1. Run migrations: `python manage.py migrate` (applies `0023`).
2. Optional: Schedule a periodic task to delete `IdempotencyRecord` rows older than 24h (or rely on the 24h filter at read time).
3. Partners: For money-moving calls (voucher issue, bulk issue, redeem PIN/OTP), send `X-Idempotency-Key` or `idempotency_key` in body for idempotent behavior; existing clients without the key behave as before.
