# Payswap – Admin Control & Approval Matrix

This document defines role hierarchy, action risk levels, who can do what, approval and audit requirements, and dangerous patterns to avoid. Use it as an SOP and audit artifact for product, ops, and senior devs.

**Based on:** Existing codebase, Technical Documentation, Self-Audit Report, Financial Safety Guarantees, and Developer Onboarding Guide.

---

## 1. Admin Role Hierarchy

| Role | Trust level | Typical access | Notes |
|------|-------------|----------------|--------|
| **Super Admin** | Highest | Django admin (all models), portal super dashboard, user/role/permission management, all high-risk actions if no extra approval is enforced | Usually `is_superuser=True` and/or role **admin** (hierarchy_level 100). Full system control. MFA required for admin/super in code. |
| **Admin** | High | Partner onboarding approval, brand approval, API key creation/revocation, pricing, service config, KYC approve/reject, settlements, logs | Role **admin** or **super** (hierarchy 100 / 90). Can perform financially impactful actions. MFA required. |
| **Employee** | Medium | Portal dashboards, voucher issuance (manual/bulk), tickets, logs view, service view, limited user management | Role **employee** (hierarchy 50). Can issue vouchers and trigger partner charges indirectly. MFA required. |
| **Support / Ops** | Medium–Low | Tickets, log view/resolve, voucher/batch view, limited config | Roles **support_agent**, **dept_manager**. No direct wallet or settlement actions in current design. |
| **Partner (API)** | External | API v2 only (vouchers, KYC, payments, SMS, BBPS, AEPS, DMT) via API key. No portal admin. | Reseller partners; usage and charges tracked by API key and partner wallet. No access to Django admin or other partners’ data. |

**Hierarchy (code):** `Role.hierarchy_level` – higher number = higher privilege. Example from setup_roles: **Admin 100**, **Super 90**, Employee 50, Distributor 40, Retailer 30, Customer 20, Vendor 10. So Admin (100) is higher than Super (90). **IsRoleOrHigher** uses `user_level >= required_level`; Admin can do everything Super can, etc.

---

## 2. Action Classification

### 🔴 HIGH RISK (money / irreversible / compliance)

- **Direct money movement:** Partner wallet credit/debit, settlement execution, refund execution.
- **Irreversible or high-impact:** API key revocation, partner suspend/activate, voucher status override (e.g. block/cancel after issue), manual balance or transaction edits.
- **Compliance / KYC:** KYC approve/reject, brand onboarding approve/reject (enables voucher issuance).

**Why high risk:** Errors cause financial loss, partner disputes, or regulatory findings. Must be logged, auditable, and ideally gated by approval or role.

---

### 🟡 MEDIUM RISK (business / partner-impacting)

- **Partner lifecycle:** Partner onboarding approve/reject, API key creation (new key grants access and chargeability).
- **Pricing and commission:** ResellerPartnerPricing create/change, ServiceCost change (affects what we charge partners).
- **Service and limits:** Service enable/disable, rate limit changes per API key (affects availability and abuse).
- **Voucher operations:** Voucher brand approve/reject, manual/bulk voucher issuance (triggers partner charge), batch process/retry.

**Why medium risk:** Affects revenue, partner capability, or operational correctness; reversible or containable with process.

---

### 🟢 LOW RISK (display / configuration / non-financial)

- **View-only:** Logs, transactions, batches, partner list, KYC list, dashboard metrics.
- **Non-financial config:** Department/agent (tickets), log resolve/unresolve, user list view, profile view.
- **Read-only admin:** IdempotencyRecord, APIKeyUsageLog (no add/change in code).

**Why low risk:** No money movement, no irreversible state change, or change is contained (e.g. ticket assignment).

---

## 3. Admin Control Matrix (TABLE)

For each action: who can do it (in current or intended design), approval required, financial impact, audit log required, reversible or not.

| Action | Who can perform | Approval required | Financial impact | Audit log required | Reversible? |
|--------|------------------|-------------------|------------------|---------------------|-------------|
| **Partner onboarding approve** | Admin, Super Admin | ⚠️ Recommended: 4-eye (e.g. Admin + Super) | Indirect (partner can then be charged) | Yes | No (approve is final; reject can be re-applied) |
| **Partner onboarding reject** | Admin, Super Admin | No (documented reason) | None | Yes | N/A |
| **Partner suspend** | Admin, Super Admin | ⚠️ Recommended: Yes | Indirect (blocks API use) | Yes | Yes (activate) |
| **Partner activate** | Admin, Super Admin | ⚠️ Recommended: Yes | Indirect | Yes | Yes |
| **API key create** | Admin, Super Admin | No (partner must exist) | Indirect (enables charging) | Yes | N/A (key is created; revoke later) |
| **API key revoke** | Admin, Super Admin | ⚠️ Recommended: Yes | Indirect (stops API access) | Yes | No (revoke is final; issue new key) |
| **Partner wallet credit** | Admin, Super Admin | ✅ MUST: 4-eye | Direct | Yes, immutable | Yes only if via proper credit txn with reference |
| **Partner wallet debit** | Admin, Super Admin | ✅ MUST: 4-eye | Direct | Yes, immutable | No (debit is final; credit to correct) |
| **Manual wallet balance edit (DB/form)** | — | ⚠️ DO NOT ALLOW | Direct | — | — |
| **Voucher brand create** | Admin, Employee (if permitted) | No | Indirect | Yes | N/A |
| **Voucher brand onboarding approve** | Admin, Super Admin | ⚠️ Recommended: 4-eye | Indirect (enables issuance) | Yes | No |
| **Voucher brand onboarding reject** | Admin, Super Admin | No | None | Yes | N/A |
| **Voucher issuance (manual single)** | Admin, Employee | No (triggers partner charge if API flow) | Indirect (partner charged) | Yes | No (voucher issued) |
| **Voucher issuance (bulk / batch process)** | Admin, Employee | No (batch created then processed) | Indirect (partner charged per commercial setup) | Yes | No |
| **Voucher cancellation / block / status override** | Admin, Super Admin | ✅ MUST: Yes | Direct (invalidates value) | Yes, immutable | No |
| **Voucher balance or PIN reset** | Admin, Super Admin | ✅ MUST: Yes | Direct | Yes, immutable | Depends (document) |
| **Pricing & commission (ResellerPartnerPricing) create/change** | Admin, Super Admin | ⚠️ Recommended: Yes | Indirect (future charges) | Yes | Yes (edit again) |
| **ServiceCost create/change** | Admin, Super Admin | ⚠️ Recommended: Yes | Indirect | Yes | Yes |
| **Settlement create** | Admin, Super Admin | No (creates record) | Indirect | Yes | N/A |
| **Settlement execute / mark paid** | Admin, Super Admin | ✅ MUST: 4-eye | Direct | Yes, immutable | No (money moved out) |
| **KYC approve** | Admin, Super Admin | ⚠️ Recommended: Yes | Compliance | Yes, immutable | No |
| **KYC reject** | Admin, Super Admin | No (reason required) | None | Yes | N/A |
| **Service enable/disable** | Admin, Super Admin | No | Indirect (availability) | Yes | Yes |
| **Rate limit change (API key)** | Admin, Super Admin | No | Indirect (abuse/throughput) | Yes | Yes |
| **Refund execution (payment/voucher)** | Admin, Super Admin | ✅ MUST: 4-eye | Direct | Yes, immutable | No |
| **Manual status override (voucher, payment, wallet)** | Admin, Super Admin | ✅ MUST: Yes | Direct or Indirect | Yes, immutable | Depends |
| **User create / role change** | Admin, Super Admin | No (role-based) | Indirect (grants capability) | Yes | Yes (revoke/change role) |
| **Permission assign/revoke** | Admin, Super Admin | No | Indirect | Yes | Yes |
| **Log resolve/unresolve** | Staff | No | None | Optional | Yes |
| **View logs / transactions / batches** | Staff (per role) | No | None | Optional (access log) | N/A |

**Notes:**

- **Approval required “Yes” or “4-eye”:** Implement via workflow (e.g. PENDING → APPROVED by second role) or policy (two people for production). Current code does not enforce 4-eye in all cases; this matrix is the target.
- **Financial impact Direct:** Action moves or commits money (wallet credit/debit, settlement paid, refund). **Indirect:** Action enables or affects future money (pricing, approve partner, enable service).
- **Audit log required Yes:** Who, when, what (before/after for critical fields). **Immutable:** Log must not be editable/deletable for compliance (RBI/fintech).

---

## 4. Approval Workflow Design

### Actions that MUST require 4-eye or second approval

- Partner wallet **credit** and **debit** (manual adjustments).
- Settlement **execute** / mark paid (money leaves the system).
- **Refund** execution (payment or voucher).
- **Voucher status override** (block, cancel, full redeem).
- **Manual balance or status override** on wallet/voucher/payment.

### Suggested approval roles

- **Initiator:** Admin or Employee (depending on action).
- **Approver:** Different person, role at least Admin (or Super Admin for wallet/settlement/refund). No self-approval.

### Suggested approval states

- **PENDING** – Request created, awaiting approver.
- **APPROVED** – Approver accepted; execute the action and log.
- **REJECTED** – Approver rejected; log reason; no execution.

Optional: **TIMEOUT** – Auto-reject or escalate if not approved within N hours (e.g. 24–72).

### Optional escalation

- If initiator and approver are the same (e.g. only one Admin), require Super Admin or escalate to designated “finance approver” role.

---

## 5. Audit & Compliance Requirements

### What must always be logged

- **Identity:** Who (user id, username, role).
- **Time:** When (UTC timestamp).
- **Action:** What (e.g. “partner_wallet_credit”, “settlement_execute”, “api_key_revoke”).
- **Target:** Which entity (partner id, wallet id, voucher id, settlement id, etc.).
- **Before/after:** For balance, status, or config: old value and new value (or diff).
- **Reason/reference:** Free text or reference_id (e.g. “Refund for order X”, “Approval ref Y”).

### Fields to capture for high-risk actions

| Field | Required | Example |
|-------|----------|--------|
| user_id / username | Yes | 123 / admin_user |
| role_code | Yes | admin |
| action | Yes | partner_wallet_credit |
| entity_type + entity_id | Yes | reseller_partner / 45 |
| amount (if money) | Yes | 1000.00 |
| balance_before / balance_after (if balance change) | Yes | 5000.00 / 6000.00 |
| reference_id / reason | Yes | ADJ-2024-001 / “Goodwill credit” |
| approved_by (if 4-eye) | Yes | 456 / super_admin |
| timestamp_utc | Yes | 2024-02-01T10:00:00Z |
| request_id / idempotency_key (if from API) | If applicable | uuid |

### Actions requiring immutable audit trails

- Partner wallet credit/debit (manual).
- Settlement execute / mark paid.
- Refund execution.
- KYC approve/reject.
- Voucher status override (block, cancel).
- API key revoke.

Store in a dedicated audit table or append-only log; no update/delete of records. Retain per RBI / internal policy (e.g. 7 years).

### Logs useful for RBI / fintech audits

- All partner wallet transactions (WalletTransaction + ResellerPartnerTransaction) with who, when, reference.
- Settlement lifecycle (create → process → complete) with amounts and payment reference.
- KYC verification and approve/reject with verification_id and reason.
- API key lifecycle (create, revoke) with reason.
- Idempotency and money-moving API calls (request_id, idempotency_key, outcome) for dispute investigation.

---

## 6. Dangerous Anti-Patterns (DO NOT ALLOW)

| Anti-pattern | Why it is dangerous | Control |
|--------------|---------------------|--------|
| **Direct DB edits** (e.g. SQL or Django shell update of Wallet.balance) | Bypasses validation, no WalletTransaction, no audit trail, can corrupt ledger. | ✅ No production DB write for wallet/voucher/transaction tables except via application code. Restrict DB access; use read replicas for ad-hoc query. |
| **One-click irreversible actions** (e.g. “Refund” or “Settlement paid” with no confirmation or approval) | Mistake causes immediate financial loss. | ✅ Require confirmation + approval workflow for refund, settlement execute, and manual wallet debit. |
| **Silent overrides without audit** (e.g. changing voucher status or wallet balance in admin without logging) | No trace for disputes or audits. | ✅ All balance/status overrides go through a service layer that writes an audit log and (for wallet) creates WalletTransaction. |
| **Manual wallet balance edit without reference** | Unreconcilable balance; no link to ticket or approval. | ✅ Every manual credit/debit must have reference_id and reason; create WalletTransaction and ResellerPartnerTransaction (if partner wallet). |
| **API key creation without partner context** | Key could be assigned to wrong partner or orphaned. | ✅ API key create only in context of a ResellerPartner; key tied to partner in DB. |
| **Pricing change without effective date or audit** | Disputes over what rate applied when. | ✅ Log before/after; consider effective_from / effective_until and change log. |
| **KYC approve without verification_id or reason** | Compliance risk; cannot prove verification was done. | ✅ Store verification_vendor, verification_id; reject requires reason. |
| **Editing IdempotencyRecord status in admin** | PENDING→COMPLETED without running business logic breaks execute-once; replay can run again. | ✅ IdempotencyRecord must be read-only in admin (all fields including status). |

---

## 7. Recommendations

### Immediate safeguards to add (if missing)

1. **Wallet balance in Django admin:** If `Wallet.balance` is editable in admin, make it **readonly** and expose manual credit/debit only via a dedicated action or portal view that calls `WalletService` / `PartnerAccountingService` and creates transactions + audit log.
2. **Partner wallet credit/debit:** Implement a single “Manual adjustment” flow (credit or debit) with mandatory reason and reference_id, 4-eye approval (PENDING → APPROVED), and immutable audit log.
3. **Settlement execute:** Do not mark settlement as paid from a single admin click; use an approval step (second role) and log approver and timestamp.
4. **Refund execution:** Same as above: approval + audit; link refund to original payment/voucher and reference.
5. **Partner onboarding approve:** Add optional 4-eye (e.g. Admin creates PENDING, Super Admin approves). At minimum, log approver and timestamp.
6. **API key revoke:** Require reason and log; consider soft-revoke (status REVOKED) and optional 24h delay before hard revoke for production.

### Admin UI warnings for high-risk actions

- **Before partner wallet credit/debit:** “This action moves real money. Ensure reference and approval are in place.”
- **Before settlement execute:** “Confirm payment has been made externally. This action cannot be undone.”
- **Before API key revoke:** “Partner will lose API access immediately. Ensure reason is documented.”
- **Before voucher block/cancel:** “Voucher value will be invalidated. Log reason for audit.”

Use modals or confirmation steps with “I have verified…” and reason field where applicable.

### Feature flags or hard blocks for production

- **Manual wallet balance edit:** Disable in production (readonly in admin); allow only via approved “Manual adjustment” flow.
- **Django admin bulk delete** on Wallet, WalletTransaction, ResellerPartnerTransaction, ResellerPartnerSettlement: Disable in production (`has_delete_permission = False` or role-based).
- **IdempotencyRecord:** Make all fields read-only in admin (including `status`). Do not allow delete (or restrict to Super Admin with audit). Editing status can break execute-once guarantees.
- **Settlement / refund:** In production, require feature flag “allow_settlement_execute” or “allow_refund” plus approval; default off for new envs until process is signed off.

---

*End of Admin Control & Approval Matrix. Use with [TECHNICAL_DOCUMENTATION.md](./TECHNICAL_DOCUMENTATION.md), [SELF_AUDIT_REPORT.md](./SELF_AUDIT_REPORT.md), [FINANCIAL_SAFETY_GUARANTEES.md](./FINANCIAL_SAFETY_GUARANTEES.md), and [DEVELOPER_ONBOARDING_GUIDE.md](./DEVELOPER_ONBOARDING_GUIDE.md).*
