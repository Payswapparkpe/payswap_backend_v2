# Payswap – Audit History (django-simple-history)

Implementation of **django-simple-history** for RBI-style immutable audit trails, aligned with [ADMIN_CONTROL_AND_APPROVAL_MATRIX.md](./ADMIN_CONTROL_AND_APPROVAL_MATRIX.md).

**Audit history is append-only and immutable for compliance.** No revert, no edit, no delete of history records.

---

## STEP 1: Installation & Versioning ✅

### Version & compatibility

- **Package:** `django-simple-history>=3.7.0,<4`
- **Django:** 4.x / 5.x / 6.x
- **Python:** 3.10+

### INSTALLED_APPS

- `simple_history` is added **after** `django_filters` and **before** `allauth`, so that:
  - Django auth and contenttypes are loaded
  - `AUTH_USER_MODEL` (`portal.User`) is available for history user attribution

### Middleware (user attribution)

- **`simple_history.middleware.HistoryRequestMiddleware`** is added **immediately after** `AuthenticationMiddleware`.
- This ensures `request.user` is set when historical records are created, so `history_user_id` is populated for portal users (and `None` for anonymous/API when no user context).

### Settings (fintech safety)

| Setting | Value | Purpose |
|--------|--------|--------|
| `SIMPLE_HISTORY_REVERT_DISABLED` | `True` | No “Revert” in admin; audit log is append-only (RBI-style). |
| `SIMPLE_HISTORY_HISTORY_ID_USE_UUID` | `False` | Integer `history_id` for indexing and joins. |
| `SIMPLE_HISTORY_DATE_INDEX` | `True` | Index on `history_date` for `as_of()` and time-range queries. |
| `SIMPLE_HISTORY_ENABLED` | `True` | Set to `False` in migrations or bulk scripts to skip history. |

### Custom user model

- `AUTH_USER_MODEL = 'portal.User'` is used.
- All `HistoricalRecords` use `user_model=settings.AUTH_USER_MODEL` so history tables reference `portal.User` for `history_user_id`.

---

## STEP 2: Selective Model Registration & Admin ✅

### Audited models (with reason)

| Model | Risk | Reason |
|-------|------|--------|
| **KYC** | HIGH | Compliance; approve/reject and verification state must be auditable. |
| **Wallet** | HIGH | Balance and status; money safety and dispute resolution. |
| **WalletTransaction** | HIGH | Every credit/debit; immutable ledger for RBI/fintech. |
| **ResellerPartnerTransaction** | HIGH | Partner revenue/commission; settlement and audit. |
| **ResellerPartnerSettlement** | HIGH | Settlement execute / mark paid; money-out audit. |
| **GiftVoucher** | HIGH | Status override, balance; voucher value and block/cancel audit. |
| **ApprovalRequest** | HIGH | 4-eye workflow; who requested, who approved, payload and result. |
| **ResellerPartner** | MEDIUM | Onboarding, status, wallet link; partner lifecycle. |
| **APIKey** | MEDIUM | Create/revoke; access and chargeability. |
| **ResellerPartnerPricing** | MEDIUM | Pricing and commission; future charges and disputes. |
| **Service** | MEDIUM | Enable/disable, config; availability and vendor config. |

**Excluded from history (per model):**

- **KYC:** `created_at`, `updated_at`
- **Wallet:** `created_at`, `updated_at`, `encrypted_seed_phrase` (sensitive)
- **WalletTransaction:** `created_at`, `encrypted_details` (sensitive)
- **GiftVoucher:** `issued_at`, `last_transaction_at`, `pin_hash`, `pin_history`, `voucher_code_hash` (secrets / auto)
- **ResellerPartner:** `created_at`, `updated_at`
- **APIKey:** `created_at`, `updated_at`, `last_used_at`, `api_key`, `api_secret`, `webhook_secret` (secrets / auto)
- **ResellerPartnerPricing:** `created_at`, `updated_at`
- **ResellerPartnerTransaction:** `created_at`, `updated_at`
- **ResellerPartnerSettlement:** `created_at`, `updated_at`
- **Service:** `created_at`, `updated_at`, `api_key`, `api_secret` (secrets / auto)
- **ApprovalRequest:** `requested_at` (auto_now_add; history_date captures when)

### Models NOT audited (with reason)

| Model | Reason |
|-------|--------|
| **IdempotencyRecord** | Execute-once; editing history could break replay semantics. MUST NOT audit. |
| **LogEntry** | Request/application log; high volume, not entity audit. |
| **APIKeyUsageLog** | Usage/analytics log; high volume, not entity audit. |
| **CashfreeAPILog** | API call log; not entity audit. |
| **GiftVoucherAuditLog** | Dedicated voucher log; avoid double-audit with simple_history. |
| **GiftVoucherOTP** | OTP/temporary; secrets, short-lived. |
| **Payment / Order** | Not present in codebase; add to audit list if introduced. |
| **User, Profile, Role** | Not in STEP 2 scope; add selectively if required. |

### Performance considerations

- **`HistoricalRecords(inherit=False, excluded_fields=[...])`** used on every audited model to reduce row size and avoid copying auto/noise fields.
- **Secrets never in history:** `encrypted_seed_phrase`, `encrypted_details`, `pin_hash`, `pin_history`, `voucher_code_hash`, `api_key`, `api_secret`, `webhook_secret` are excluded.
- **Bulk writes:** For voucher bulk issue or batch processing, use `bulk_create_with_history()` / `bulk_update_with_history()` from `simple_history.utils` inside the **same** `transaction.atomic()` as the business write so history commits or rolls back with the main data.
- **No history on abstract bases:** Only concrete models have `HistoricalRecords`; no abstract model auditing.
- **No dynamic `register()`:** All registration is inline on the model; no signals or custom save hooks for history.

### Fintech safety (non-negotiable)

- History rows are written inside the **same DB transaction** as the main model save/update/delete (django-simple-history uses post_save/post_delete by default; they run in the same transaction).
- If wallet debit or voucher redeem rolls back → the corresponding history insert rolls back.
- Idempotent retries: business logic should only perform actual state change (e.g. reserve-before-execute); then at most one save/update runs per key, so at most one history row per change. Do not create history on read-only operations.
- No audit rows for read-only operations; history is created only on create/update/delete of the audited model.

### Admin configuration (audit lockdown)

- All historical models are registered with **ReadOnlyHistoryAdmin** (subclass of `SimpleHistoryAdmin`):
  - **No add:** `has_add_permission = False`
  - **No delete:** `has_delete_permission = False`
  - **View only:** `has_change_permission = True` but **all fields readonly** via `get_readonly_fields` so staff can view list and detail but cannot edit.
- **Revert:** Disabled globally via `SIMPLE_HISTORY_REVERT_DISABLED = True`.
- **Filter/search:** `history_date`, `history_user`, `history_type`, `id` (object_id) are available in list filter and search.

---

## Migrations

- **Migration:** `portal/migrations/0026_add_simple_history_tables.py`
- Creates historical tables for: KYC, Wallet, WalletTransaction, GiftVoucher, ResellerPartner, APIKey, ResellerPartnerPricing, ResellerPartnerTransaction, ResellerPartnerSettlement, Service, ApprovalRequest.
- Apply with: `python manage.py migrate portal`.

---

## Why some models are excluded

- **IdempotencyRecord:** Status (PENDING → COMPLETED/FAILED) is part of execute-once semantics. Auditing it could imply history is editable or replayable; we keep it out of simple_history and treat it as operational data only.
- **LogEntry, APIKeyUsageLog, CashfreeAPILog:** High-volume request/API logs; not entity-level audit. Kept separate for performance and clarity.
- **GiftVoucherOTP:** Contains OTP values; short-lived and sensitive; not needed for long-term audit.

---

## How performance is preserved

1. **Excluded fields:** Auto timestamps and secrets are excluded so history rows are smaller and fewer columns are written.
2. **No history on logs or idempotency:** High-write tables (logs, idempotency) are not audited.
3. **Bulk paths:** Use `bulk_create_with_history` / `bulk_update_with_history` in the same `transaction.atomic()` as the main bulk write so we avoid N single-row history inserts and keep transaction boundaries correct.
4. **Same transaction:** History is created in the same transaction as the model change; no extra commit round-trip for audit.

---

## References

- [django-simple-history docs](https://django-simple-history.readthedocs.io/en/stable/)
- [ADMIN_CONTROL_AND_APPROVAL_MATRIX.md](./ADMIN_CONTROL_AND_APPROVAL_MATRIX.md) – audit requirements and immutable log rules
