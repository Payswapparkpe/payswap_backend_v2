# Financial Safety Guarantees (Execute-At-Most-Once)

Summary of guarantees achieved for money-moving operations under concurrency.

---

## 1. Strong idempotency (execute at most once per key)

**Mechanism**

- `IdempotencyRecord` has `status`: PENDING | COMPLETED | FAILED; response fields are nullable when PENDING.
- At the **start** of the request, inside `transaction.atomic()`, we try to **INSERT** (scope, idempotency_key, status=PENDING).
- If the row already exists: **COMPLETED** → return stored response; **PENDING** or **FAILED** → return **409 Conflict**.
- Only the request that successfully creates PENDING runs business logic.
- After success: `complete_idempotency(scope, key, status_code, body)`; on exception: `fail_idempotency(scope, key)`.

**Applied to**

- Voucher issue (single + bulk)
- Voucher redeem (PIN + OTP)

**Guarantee**

- Money-moving operations execute **at most once** per idempotency key under concurrent requests. Duplicate keys get either the stored response (replay) or 409 (in progress / failed).

---

## 2. Partner charge: at most one debit per (partner, reference_id)

**Mechanism**

- DB unique constraint on `ResellerPartnerTransaction`: (partner, reference_id) unique when transaction_type=REVENUE and reference_id is not null/empty.
- In `charge_partner_for_service` when reference_id is set:
  - Inside **one** `transaction.atomic()`: try to **create** REVENUE with status=PENDING (reserves reference_id).
  - On **IntegrityError**: fetch existing REVENUE and return it **without debiting** the wallet.
  - Otherwise: lock wallet (`select_for_update`), check balance, debit, create WalletTransaction, update REVENUE to COMPLETED.
  - Commission is created via `_ensure_commission_for_revenue` after the atomic block.

**Guarantee**

- At most one wallet debit per (partner, reference_id). Concurrent requests with the same reference_id: one creates PENDING and debits; others get IntegrityError and return the existing transaction without debiting.

---

## 3. Other guarantees (unchanged)

- **Double voucher redemption:** Prevented by `select_for_update()` on the voucher row and re-validation of status/balance inside `transaction.atomic()` in PIN and OTP redeem.
- **Partner wallet balance cannot go negative:** Balance check after wallet lock; debit, WalletTransaction, and REVENUE/COMPLETED in one atomic block.
- **Partial wallet debits:** All debit steps (lock, check, debit, WalletTransaction create) in a single `transaction.atomic()`; no intermediate commit.

---

*See SELF_AUDIT_REPORT.md for full re-review and remaining non-financial risks.*
