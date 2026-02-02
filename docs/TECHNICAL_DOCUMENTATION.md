# Payswap – Complete Technical Documentation

A single structured document for new developers, product owners, and auditors to understand the project from A to Z without reading the full codebase.

---

## 1. Project Overview

### What Problem This Project Solves

**Payswap** is a fintech technology platform that provides:

- **Digital payment infrastructure** – BBPS (bill payments), AEPS (Aadhaar payments), DMT (domestic money transfer), payment gateway (Cashfree PG).
- **Prepaid and stored value** – Gift voucher issuance, redemption, PIN/OTP flows, bulk issuance, brand and client management.
- **Identity and compliance** – KYC/verification (PAN, Aadhaar, bank, driving licence, voter ID, passport, GST, face match/liveness) via Cashfree/Invincible Ocean.
- **Partner and reseller model** – Reseller partners onboard, get API keys, use vouchers/KYC/payments/SMS/BBPS/AEPS/DMT; wallet, pricing, settlements, and usage tracking.
- **Internal operations** – User/role/permission management, ticket management, wallet, logs, services configuration, and admin partner management.

### Target Users

- **Internal staff** – Admin, Employee, Super (portal dashboards, tickets, logs, services, voucher brands/clients/batches).
- **Distributors / Retailers / Vendors / Customers** – B2B/B2C roles with role-specific dashboards and KYC where required.
- **API partners (resellers)** – External businesses with API keys; consume voucher, KYC, payment, SMS, BBPS, AEPS, DMT APIs.
- **End consumers** – Recipients of vouchers, bill payers, AEPS/DMT users (indirectly via partners).

### High-Level System Purpose

Deliver a **secure, API-first, multi-tenant** backend that:

- Exposes **internal portal** (Django templates, session auth, MFA) for staff and B2B/B2C users.
- Exposes **versioned REST APIs** – v1 for internal/authenticated users, v2 for external partners (API key auth).
- Integrates **third-party vendors** (Kaleyra SMS, Cashfree verification/PG, Mobikwik/Euronet BBPS, PayPoint AEPS/DMT, Leegality, etc.).
- Runs **async workloads** (Celery) for bulk voucher processing, notifications, OTP, logging, and cleanup.

---

## 2. Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.12+, Django 6.x, Django REST Framework |
| **Database** | PostgreSQL 16+ (via `dj-database-url`) |
| **Cache / broker / results** | Redis (cache, Celery broker, Celery result backend) |
| **Async tasks** | Celery, django-celery-beat, django-celery-results |
| **API docs** | drf-spectacular (OpenAPI/Swagger/ReDoc) |
| **Auth (portal)** | Django session, django-allauth (Google/Facebook/Apple), MFA (TOTP/SMS OTP) |
| **Auth (API v2)** | API key (X-API-Key or Bearer), optional IP whitelist |
| **Frontend (portal)** | Django templates, HTMX-friendly, Bootstrap-style UI |
| **Frontend (optional)** | Angular workspace in `frontend-space/` (Parkpe, Payswap landing apps) |
| **SMS/OTP** | Kaleyra (India) |
| **Email** | SMTP (configurable); separate Parkpe SMTP for voucher emails |
| **Payments** | Cashfree PG (SANDBOX/PRODUCTION) |
| **KYC/Verification** | Cashfree, Invincible Ocean; Leegality for document signing |
| **BBPS** | Mobikwik, Euronet (Bharat Connect / EFT APME) |
| **AEPS/DMT** | PayPoint India |
| **Storage** | Local media; optional S3 (boto3) for documents |
| **Config** | Pydantic Settings (`core/config.py`), `.env` |
| **Logging** | Python logging, file + console; optional DB log entries and async write task |
| **Monitoring** | Sentry (optional; currently disabled in code due to dependency conflict) |

### Infrastructure Assumptions

- PostgreSQL and Redis are available (local or managed).
- Celery workers and (optionally) Celery Beat run as separate processes.
- In production: HTTPS, non-debug, `ALLOWED_HOSTS` and CORS set appropriately.
- Optional: S3 for KYC/brand documents; SMTP and Kaleyra for email/SMS.

---

## 3. System Architecture

### High-Level (Logical)

- **Portal app (`portal`)**: Web UI (signin, signup, MFA, dashboards, profile, users, KYC, wallet, permissions, logs, tickets, services, voucher brands/clients/batches, VoucherX, reseller/partner onboarding and API keys). Serves HTML; session-based auth; MFA and profile-completion middleware.
- **API app (`api`)**: REST APIs only.
  - **v1**: Internal – session/auth required; used by staff/frontend; tickets, dashboard, vouchers (issue/redeem/reports), departments, agents.
  - **v2**: External – API key auth; vouchers, KYC, payments, SMS, BBPS, AEPS, DMT; partner usage and (where applicable) partner wallet charging.
- **Core (`core`)**: Django settings, config (Pydantic), URL root, Celery app. Middleware: CORS, request ID, API key IP whitelist, API key usage logging, request logging, profile completion, MFA.
- **Celery**: Async tasks (voucher bulk processing, SMS, email, OTP dual delivery, write logs, clean old logs, notification tasks). Broker and result backend: Redis.
- **External vendors**: Kaleyra, Cashfree (verification + PG), Mobikwik BBPS, Euronet BBPS, PayPoint AEPS/DMT, Leegality – called from services in `portal/services/` and `portal/services/vendors/`.

### Module-Wise Breakdown

| Module | Purpose |
|--------|--------|
| **portal** | Models (User, Profile, Role, KYC, Wallet, Permissions, LogEntry, Service, Ticket, GiftVoucher*, ResellerPartner, APIKey, etc.), views, URLs, middleware, permissions, forms, admin, services, tasks, templating. |
| **api** | v1 and v2 URLs and views; mixins (response, logging); v2 auth (API key), permissions, throttling, serializers; middleware (request ID). |
| **core** | Settings, config (Pydantic), Celery app, URL routing (admin, api, accounts, portal). |

### How Components Interact

- **Request flow**: Client → Django (middleware) → URL router → Portal or API view → Service layer (optional) → Model/DB and/or external HTTP (vendors) → Response. API responses use `StandardResponseMixin` (success/error with `request_id`, `response_id`).
- **Auth**: Portal uses session + MFA; API v1 uses session (IsInternalUser/IsStaffOnly); API v2 uses API key (APIKeyAuthentication, HasAPIKey, HasServicePermission). API key usage can be logged and IP-whitelisted.
- **Money flows**: Partner-facing APIs (e.g. voucher issue, KYC) can charge the reseller partner’s wallet via `PartnerAccountingService` using `ResellerPartnerPricing` and `Service`/cost configuration.
- **Async**: Views enqueue Celery tasks (e.g. bulk voucher issuance, send SMS/email/OTP, write log entry); workers run tasks and may call the same services (e.g. `VoucherService`, `BulkVoucherService`).

---

## 4. Authentication & Authorization

### User Roles (Portal)

- **super** – Superuser; highest privilege.
- **admin** – Admin; manage partners, brands, users, etc.
- **employee** – Internal employee.
- **distributor**, **retailer**, **customer**, **vendor** – B2B/B2C.
- **support_agent**, **dept_manager** – Ticket management.
- **api_partner**, **partner** – API/reseller context.
- **super_distributor** – Distributor hierarchy.

Roles are stored in `portal.Role` (code, name, category, hierarchy_level, mfa_required, default_permissions). User has `role` (FK) and `role_code` (denormalized).

### Auth Flow (Portal)

1. **Sign-in**: Username (or email) + password. Login uses Django auth; failed attempts increment `failed_login_attempts`; after 10 failures account is locked for 30 minutes.
2. **Pre-conditions**: User must be active, email verified; if role requires MFA, MFA must be configured; for some roles (e.g. customer, vendor) KYC may be required.
3. **MFA**: If role requires MFA and not configured → redirect to MFA setup. Methods: OTP (SMS via Kaleyra) or Authenticator (TOTP). After setup, MFA verify step before full access.
4. **Profile completion**: Social signup can set `profile_completion_required`; middleware redirects to profile complete until done.
5. **Session**: Django session in Redis (`SESSION_ENGINE = cache`), cookie name `payswap_sessionid`; CSRF cookie `payswap_csrftoken`.

### Token / Session Handling

- **Portal**: Session-only; no JWT for browser. Session cookie HttpOnly, SameSite=Lax; secure in production.
- **API v1**: Session authentication (same as portal when called from a logged-in browser).
- **API v2**: API key only. Key sent via `X-API-Key` or `Authorization: Bearer <key>`. Key is looked up (hashed) via `APIKeyService.find_api_key_by_plain_key`; partner and key attached to `request`; no session.

JWT settings exist in config (`JWT_SIGNING_KEY`, lifetimes) but are not used in the current portal/API flows described above; they are available for future use.

### Security Assumptions (Auth)

- API keys are stored hashed; plain key shown only once at creation.
- MFA is enforced for admin/employee/super/distributor roles.
- Account lockout and failed-attempt tracking reduce brute-force risk.
- Profile completion and KYC gates ensure required data before sensitive actions.

---

## 5. Database Design

### All Tables / Models (portal)

| Model | Table | Purpose |
|-------|--------|--------|
| **User** | portal_user | Custom user: username, role, role_code, MFA fields, KYC flags, lockout, email (nullable, synced from Profile). |
| **Profile** | portal_profile | OneToOne User: name, email, phone, address, banking (encrypted), tax IDs, notification prefs, verification flags, social provider. |
| **Role** | portal_role | Role definition: code, name, category, hierarchy_level, mfa_required, default_permissions. |
| **KYC** | portal_kyc | OneToOne User: status, document_type, document_number, verification_vendor, verification_id, verification_response. |
| **Wallet** | portal_wallet | OneToOne User: balance, currency, status, encrypted_seed_phrase, wallet_address. |
| **WalletTransaction** | portal_wallet_transaction | FK Wallet: type, amount, balance_before/after, reference, status, encrypted_details. |
| **UserPermission** | portal_user_permission | User + Permission (Django) assignment; granted_by, is_active, revoked_at. |
| **LogEntry** | portal_logentry | Central log: timestamp, level, category, message, module_name, url, request_id, user, request_meta, response_meta, etc. |
| **CashfreeAPILog** | portal_cashfreeapilog | Cashfree API request/response log. |
| **Service** | portal_service | Service definition: name, code, status, vendor_config (JSON), is_enabled, etc. |
| **ServiceCost** | portal_service_cost | FK Service: cost_type, base_cost, cost_percentage, tiered_cost; for margin/pricing. |
| **BBPSBillerCategory** | portal_bbpsbillercategory | BBPS biller category and commission config. |
| **RBIRuleConfiguration** | portal_rbiruleconfiguration | RBI rule config (e.g. limits). |
| **Department** | portal_department | Ticket departments. |
| **Agent** | portal_agent | Ticket agents (User FK). |
| **Ticket** | portal_ticket | Ticket: subject, status, priority, department, agent, requester, etc. |
| **TicketNote** | portal_ticketnote | FK Ticket: notes. |
| **TicketAssignmentHistory** | portal_ticketassignmenthistory | Ticket assignment history. |
| **TicketAttachment** | portal_ticketattachment | FK Ticket: file. |
| **GiftVoucherBrand** | portal_gift_voucher_brand | Brand: brand_code, api_identifier, onboarding_status, bank/docs, agreement. |
| **VoucherClient** | portal_voucher_client | FK Brand: client_code, client_name, contact. |
| **GiftVoucher** | portal_gift_voucher | FK Brand: voucher_code, pin_hash, amount, balance, status, client, issuer, metadata. |
| **GiftVoucherTransaction** | portal_gift_voucher_transaction | FK GiftVoucher: type, amount, reference, balance_after, etc. |
| **GiftVoucherOTP** | portal_gift_voucher_otp | OTP for voucher redemption; expiry, attempts. |
| **BulkVoucherIssuanceBatch** | portal_bulk_voucher_issuance_batch | Bulk batch: brand, client, status, denomination_breakdown or file path, metadata, progress. |
| **GiftVoucherAuditLog** | portal_gift_voucher_audit_log | Audit trail for voucher actions. |
| **ResellerPartner** | portal_reseller_partner | Partner: partner_code, company, contact, status, onboarding_status, wallet FK. |
| **APIKey** | portal_apikey | FK ResellerPartner: key hash, key_prefix, permissions (JSON), rate_limit (JSON), ip_whitelist (JSON), expires_at. |
| **APIKeyUsageLog** | portal_apikeyusagelog | Per-request API key usage log. |
| **ResellerPartnerPricing** | portal_reseller_partner_pricing | Partner + Service pricing: base_price, percentage, etc. |
| **ResellerPartnerTransaction** | portal_reseller_partner_transaction | Partner wallet transactions (charges/credits). |
| **ResellerPartnerSettlement** | portal_reseller_partner_settlement | Settlement runs for partners. |

(Plus Django built-in: auth_group, auth_permission, auth_user_groups, etc.; sites, socialaccount, etc.)

### Important Relationships

- User ↔ Profile: OneToOne. User ↔ Role: FK. User ↔ Wallet: OneToOne via Wallet.user. User ↔ KYC: OneToOne.
- GiftVoucher → GiftVoucherBrand, optional VoucherClient, issued_by User. GiftVoucherTransaction → GiftVoucher.
- BulkVoucherIssuanceBatch → Brand, Client, created_by, issued_by.
- ResellerPartner → Wallet (optional). APIKey → ResellerPartner. ResellerPartnerPricing → ResellerPartner, Service.
- Ticket → Department, Agent (User), requester. TicketNote, TicketAttachment → Ticket.
- Service ↔ ServiceCost; BBPSBillerCategory linked to service/vendor config where used.

### Important Fields (Summary)

- **User**: username (unique), role_code, mfa_enabled, mfa_configured, totp_secret (encrypted), kyc_completed, account_locked_until, failed_login_attempts.
- **Profile**: email (unique), phone (unique), encrypted_banking_details, email_verified, phone_verified, profile_completion_required.
- **GiftVoucher**: voucher_code, pin_hash, amount, balance_remaining, status (e.g. ISSUED, REDEEMED, EXPIRED), client_id, metadata.
- **APIKey**: api_key (hash), permissions e.g. `{ "voucher": ["issue", "redeem"], "kyc": ["pan"] }`, rate_limit, ip_whitelist.
- **BulkVoucherIssuanceBatch**: status (PENDING, PROCESSING, COMPLETED, FAILED), denomination_breakdown or uploaded_file_path, metadata (progress).

### Indexes and Constraints

- Indexes on: Profile (email, phone, status); User; LogEntry (timestamp, log_level, category, request_id, user); Service (code, status); GiftVoucherBrand (brand_code, status, onboarding_status); BulkVoucherIssuanceBatch (status, brand, created_at); ResellerPartner, APIKey (partner, status, expires_at); WalletTransaction (wallet, created_at; status, created_at).
- Unique: User.username; Profile.email, Profile.phone; APIKey.api_key; GiftVoucherBrand.brand_code, api_identifier; VoucherClient.client_code; Wallet.wallet_address. Unique_together: UserPermission (user, permission).

---

## 6. Core Business Logic

### Voucher Issuance (Single)

1. Validate brand (api_identifier or brand_code or brand_id) and amount; recipient email required for API.
2. `VoucherService.issue_single_voucher`: generate voucher_code and PIN, create GiftVoucher and initial transaction, optionally send email (Parkpe SMTP).
3. If API v2 and partner: charge partner wallet via PartnerAccountingService (ResellerPartnerPricing for voucher service).
4. Return voucher_code, pin (once), amount, reference_number, etc.

### Voucher Issuance (Bulk)

1. Create BulkVoucherIssuanceBatch (MANUAL_BULK with denomination_breakdown or FILE_UPLOAD with S3 path).
2. Set status to PROCESSING (or PENDING and enqueue task).
3. Celery task `process_bulk_voucher_issuance_task`: for each row (denomination or CSV row), create GiftVoucher, update batch metadata progress, handle errors per row.
4. On completion set batch status to COMPLETED or FAILED; store error_log if any.
5. Idempotency: task checks batch status and metadata; can resume from current_voucher_index in metadata.

### Voucher Redemption

- **PIN**: Validate voucher_code + PIN (hash compare); deduct amount (or full balance); create GiftVoucherTransaction; update balance; optional PIN lockout after failed attempts.
- **OTP**: Request OTP to mobile → create GiftVoucherOTP; verify OTP then same debit/transaction flow as PIN. OTPs expire; expired/used OTPs cleaned by periodic task.

### Partner Charging (API v2)

- After successful voucher issue or KYC call, `PartnerAccountingService.charge_partner_for_service` loads Service and ResellerPartnerPricing for that partner, computes amount (e.g. voucher amount or fixed KYC fee), creates ResellerPartnerTransaction (debit) and updates partner wallet balance. Failures can be logged and optionally returned.

### BBPS Flow (Euronet / Mobikwik)

1. Operators: list billers/operators by category (from vendor API or cached).
2. Fetch bill: operator_id, customer_id → vendor fetch bill API → return bill details.
3. Pay bill: operator_id, customer_id, amount, ref_id → vendor pay API → return ref_id/status.
4. Status: ref_id → vendor status API → return payment status.

Vendor selection by `vendor` query param or config; credentials and URLs from `core.config` (Euronet/Mobikwik).

### AEPS / DMT (PayPoint)

- Credentials (UserCode, Password, IdentificationCode) encrypted via PayPoint Encrypt API before each request. Balance, withdrawal, mini-statement, transaction status, agent registration/update/auth/2FA as per PayPoint docs. DMT: register sender, add beneficiary, remit, status, list beneficiaries.

### KYC (Cashfree / Invincible Ocean)

- PAN, Aadhaar, bank, driving licence, voter ID, passport, GST, face match, face liveness: upload or pass document/ID and call verification service; store verification_id and response; return status. Partner charged per verification when using API v2.

### Error Handling and Safety

- API responses: standardized success/error via StandardResponseMixin; errors list and message; 4xx/5xx status codes.
- Bulk voucher: per-row try/except; batch-level error_log; status FAILED on critical failure.
- Wallet: transactions in DB transactions; balance updates consistent with WalletTransaction records.
- Idempotency: bulk batch processing uses batch status and metadata to avoid double-processing; payment/order idempotency can be added per endpoint if required (not fully documented in code).

---

## 7. API Documentation

### Response Structure (All APIs)

Success:

```json
{
  "success": true,
  "message": "Operation completed successfully",
  "request_id": "uuid",
  "response_id": "uuid",
  "timestamp": "ISO8601",
  "data": { ... }
}
```

Error:

```json
{
  "success": false,
  "message": "Error message",
  "request_id": "uuid",
  "response_id": "uuid",
  "timestamp": "ISO8601",
  "errors": [ { "message": "...", "field": "..." } ]
}
```

Headers: `X-Request-ID`, `X-Response-ID` when available.

### API v1 (Internal)

Base path: `/api/v1/`. Auth: Session (Django). Permission: IsInternalUser or IsStaffOnly (per view).

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /api/v1/health/ | Internal | Health check. |
| GET | /api/v1/dashboard/overview/ | Internal | Dashboard overview. |
| GET | /api/v1/dashboard/agent-performance/ | Internal | Agent performance. |
| GET | /api/v1/dashboard/department-stats/ | Internal | Department stats. |
| GET | /api/v1/analytics/tickets-by-status/ | Internal | Tickets by status. |
| GET | /api/v1/analytics/resolution-time/ | Internal | Resolution time. |
| GET/POST | /api/v1/departments/ | Internal | Departments CRUD. |
| GET/POST | /api/v1/agents/ | Internal | Agents CRUD. |
| GET/POST/PATCH | /api/v1/tickets/ | Internal | Tickets CRUD. |
| GET/POST | /api/v1/vouchers/brands/ | Internal | Voucher brands. |
| GET/POST | /api/v1/vouchers/clients/ | Internal | Voucher clients. |
| POST | /api/v1/vouchers/issue/single/ | Internal | Issue single voucher. |
| POST | /api/v1/vouchers/issue/bulk/ | Internal | Create bulk batch. |
| GET | /api/v1/vouchers/issue/bulk/<batch_id>/status/ | Internal | Bulk batch status. |
| POST | /api/v1/vouchers/redeem/pin/ | Internal | Redeem by PIN. |
| POST | /api/v1/vouchers/redeem/otp/request/ | Internal | Request OTP. |
| POST | /api/v1/vouchers/redeem/otp/verify/ | Internal | Verify OTP and redeem. |
| POST | /api/v1/vouchers/pin/change/request/ | Internal | Request PIN change. |
| POST | /api/v1/vouchers/pin/change/verify/ | Internal | Verify PIN change. |
| GET | /api/v1/vouchers/balance/ | Internal | Voucher balance (body: voucher_code). |
| GET | /api/v1/vouchers/reports/issuance/ | Internal | Issuance report. |
| GET | /api/v1/vouchers/reports/redemption/ | Internal | Redemption report. |
| GET | /api/v1/vouchers/reports/outstanding/ | Internal | Outstanding balance report. |
| GET | /api/v1/vouchers/batches/<batch_id>/export/ | Internal | Export batch. |

Request/response bodies follow DRF serializers; see `api/v1/` serializers and views for exact fields.

### API v2 (External – API Key)

Base path: `/api/v2/`. Auth: `X-API-Key` or `Authorization: Bearer <api_key>`. Permission: HasAPIKey; many views also HasServicePermission (e.g. voucher.issue, kyc.pan).

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /api/v2/health/ | None | Health check. |
| GET | /api/v2/public/ | None | Public demo. |
| GET | /api/v2/partner/ | API Key | Partner demo. |
| POST | /api/v2/vouchers/issue/ | API Key + voucher.issue | Issue single voucher. Body: api_identifier or brand_id or brand_code, amount, email, optional mobile_number, client_id, metadata. |
| POST | /api/v2/vouchers/bulk-issue/ | API Key + voucher.issue | Bulk issue. Body: brand_id, denominations { amount: { quantity: n } }, optional client_id. |
| POST | /api/v2/vouchers/redeem-pin/ | API Key | Redeem by PIN. Body: voucher_code, pin, optional amount. |
| POST | /api/v2/vouchers/redeem-otp/request/ | API Key | Request OTP. Body: voucher_code, mobile_number. |
| POST | /api/v2/vouchers/redeem-otp/verify/ | API Key | Verify OTP and redeem. Body: voucher_code, otp, optional amount. |
| GET | /api/v2/vouchers/<voucher_code>/balance/ | API Key | Balance for voucher_code. |
| POST | /api/v2/vouchers/<voucher_code>/pin/change/request/ | API Key | Request PIN change. |
| POST | /api/v2/vouchers/<voucher_code>/pin/change/verify/ | API Key | Verify PIN change. |
| GET | /api/v2/vouchers/batches/ | API Key | List batches. |
| GET | /api/v2/vouchers/batches/<batch_id>/ | API Key | Batch detail. |
| POST | /api/v2/kyc/pan/verify/ | API Key + kyc.pan | PAN verification. |
| POST | /api/v2/kyc/aadhaar/verify/ | API Key | Aadhaar verification. |
| POST | /api/v2/kyc/bank/verify/ | API Key | Bank verification. |
| POST | /api/v2/kyc/driving-license/verify/ | API Key | Driving licence. |
| POST | /api/v2/kyc/voter-id/verify/ | API Key | Voter ID. |
| POST | /api/v2/kyc/passport/verify/ | API Key | Passport. |
| POST | /api/v2/kyc/gst/verify/ | API Key | GST. |
| POST | /api/v2/kyc/face-match/ | API Key | Face match. |
| POST | /api/v2/kyc/face-liveness/ | API Key | Face liveness. |
| GET | /api/v2/kyc/verifications/<verification_id>/ | API Key | Verification status. |
| POST | /api/v2/payments/initiate/ | API Key | Initiate payment (Cashfree PG). |
| GET | /api/v2/payments/<payment_id>/status/ | API Key | Payment status. |
| POST | /api/v2/payments/<payment_id>/refund/ | API Key | Refund. |
| GET | /api/v2/payments/ | API Key | List payments. |
| POST | /api/v2/sms/send/ | API Key | Send SMS. |
| POST | /api/v2/sms/otp/send/ | API Key | Send OTP SMS. |
| POST | /api/v2/sms/otp/verify/ | API Key | Verify OTP. |
| GET | /api/v2/sms/delivery-status/<message_id>/ | API Key | Delivery status. |
| GET | /api/v2/bbps/operators/ | API Key | BBPS operators (query: category, vendor). |
| POST | /api/v2/bbps/bill/fetch/ | API Key | Fetch bill. |
| POST | /api/v2/bbps/bill/pay/ | API Key | Pay bill. |
| GET | /api/v2/bbps/bill/status/<ref_id>/ | API Key | Bill payment status. |
| POST | /api/v2/aeps/balance/ | API Key | AEPS balance. |
| POST | /api/v2/aeps/withdrawal/ | API Key | AEPS withdrawal. |
| POST | /api/v2/aeps/mini-statement/ | API Key | AEPS mini statement. |
| GET | /api/v2/aeps/status/<ref_id>/ | API Key | AEPS transaction status. |
| POST | /api/v2/aeps/agent-registration/ | API Key | Agent registration. |
| POST | /api/v2/aeps/update-agent-details/ | API Key | Update agent. |
| POST | /api/v2/aeps/agent-service-status/ | API Key | Service status. |
| POST | /api/v2/aeps/agent-authentication/ | API Key | Agent auth. |
| POST | /api/v2/aeps/two-factor-auth/ | API Key | 2FA. |
| POST | /api/v2/dmt/register-sender/ | API Key | DMT register sender. |
| POST | /api/v2/dmt/add-beneficiary/ | API Key | Add beneficiary. |
| POST | /api/v2/dmt/remit/ | API Key | DMT remit. |
| GET | /api/v2/dmt/status/<ref_id>/ | API Key | DMT transaction status. |
| GET | /api/v2/dmt/beneficiaries/ | API Key | List beneficiaries. |

Possible error responses: 400 (validation), 401 (invalid/missing API key), 403 (permission denied or IP not allowed), 404 (resource not found), 429 (rate limit). Body: standard error JSON with `errors` array.

OpenAPI schema: `/api/schema/`; Swagger UI: `/api/schema/swagger-ui/`; ReDoc: `/api/schema/redoc/`.

---

## 8. Background Jobs / Cron / Workers

### Celery Tasks

| Task | Purpose | Trigger | Retry / failure |
|------|--------|--------|-----------------|
| process_bulk_voucher_issuance | Process bulk voucher batch (create vouchers, update progress) | Enqueued when bulk batch is created/started | bind=True, max_retries=3 |
| send_sms | Send SMS via Kaleyra | Enqueued by notification/sms flow | max_retries=3 |
| send_email | Send email (SMTP) | Enqueued by notification/email flow | max_retries=3 |
| send_otp_sms | Send OTP SMS | OTP request flows | max_retries=3 |
| send_otp_dual | Send OTP via SMS + email | Dual delivery flow | max_retries=3 |
| send_notification | Generic notification | Enqueued by notification service | - |
| write_logs | Write log entry (e.g. to DB or file) | Enqueued by views/middleware/services | max_retries=3 |
| clean_old_logs | Delete log files older than retention | Manual or Celery Beat (if configured) | - |
| log_user_action, log_api_call, log_security_event, log_generic | Structured logging to DB | Enqueued by callers | - |
| batch_log_cleanup | Clean old log entries (DB) | Manual or Beat | - |
| cleanup_expired_voucher_otps | Remove expired GiftVoucherOTP | Periodic (Beat) or manual | - |
| unblock_pin_locked_vouchers | Unlock PIN-locked vouchers after cooldown | Periodic (Beat) or manual | - |

Celery Beat: No `CELERY_BEAT_SCHEDULE` was found in the codebase; periodic tasks (clean_old_logs, cleanup_expired_voucher_otps, unblock_pin_locked_vouchers) can be added to Beat or run via cron/manual.

### Retry and Failure Handling

- Tasks with `max_retries=3` use Celery retry; failures can be logged and/or dead-lettered depending on configuration.
- Bulk voucher task updates batch status to FAILED and error_log on critical failure; partial progress is stored in batch metadata.

---

## 9. Logging & Monitoring

### What Is Logged

- **RequestLoggingMiddleware**: For each request (excluding static/media/health): method, path, user, IP, user-agent, response status, duration; can enqueue `write_logs_task` with request_id, response_id.
- **LogEntry (DB)**: level, category (api, auth, payment, notification, security, cashfree, kaleyra, gift_voucher, general, etc.), message, module_name, url, request_id, user, request_meta, response_meta, extra_data.
- **CashfreeAPILog**: Cashfree API request/response for debugging.
- **APIKeyUsageLog**: API key ID, endpoint, timestamp (when API key usage logging middleware is enabled).
- **Voucher**: `log_voucher_operation` and GiftVoucherAuditLog for issuance, redemption, PIN change, etc.

### Where Logs Are Stored

- **Files**: `logs/portal.log` (rotating, e.g. 10 MB × 5), `logs/portal_errors.log` (errors). Path configurable via PAYSWAP_LOG_DIR.
- **Database**: LogEntry, CashfreeAPILog, APIKeyUsageLog.
- **Console**: Django loggers output to console (verbose format).

### How Failures Are Traced

- request_id and response_id in responses and log entries; correlation via X-Request-ID / X-Response-ID.
- Log level and category filter in admin/portal log list views.
- Sentry is configured in settings but currently disabled (comment in settings.py) due to dependency conflict with cashfree_pg.

---

## 10. Security Considerations

- **Data protection**: Sensitive fields (bank details, TOTP secret, PAN/Aadhaar where stored) use encryption (Fernet/symmetric) via `portal.utils.encryption`. API keys stored hashed.
- **Input validation**: DRF serializers and model validators; phone/PAN/Aadhaar validators in portal. File uploads (KYC, attachments) validated by type/size where implemented.
- **Rate limiting**: API v2: APIKeyRateThrottle (per key), ServiceRateThrottle (per service), PartnerRateThrottle (per partner). Limits configurable per key (rate_limit JSON) or default (e.g. 100/min, 1000/hour per key).
- **CORS**: Allowed origins from config (CORS_ALLOWED_ORIGINS); credentials true.
- **CSRF**: Required for portal forms; CSRF_TRUSTED_ORIGINS for API/frontend origins when needed.
- **Headers**: SECURE_BROWSER_XSS_FILTER, SECURE_CONTENT_TYPE_NOSNIFF, X_FRAME_OPTIONS DENY; HSTS in production.
- **IP whitelist**: API key can have ip_whitelist; APIKeyIPWhitelistMiddleware enforces it for v2.
- **Known risks / TODOs**: Sentry disabled; some validations (e.g. file type/size) may not be uniform; idempotency keys not documented for all financial endpoints; dependency on third-party vendors (Kaleyra, Cashfree, etc.) for availability and security.

---

## 11. Environment Configuration

### Required Environment Variables

- **Application**: SECRET_KEY, DEBUG, ALLOWED_HOSTS, APP_ENV (development|staging|production), TIMEZONE.
- **Database**: DATABASE_URL (PostgreSQL).
- **Redis**: REDIS_URL.
- **Celery**: CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CELERY_TIMEZONE.
- **Security**: ENCRYPTION_KEY, SIGNING_SECRET, JWT_SIGNING_KEY (min length 32 each).
- **SMS**: KALEYRA_API_KEY, KALEYRA_SID; optional KALEYRA_HEADER_PAYSWAP, KALEYRA_OTP_TEMPLATE_ID, KALEYRA_BASE_URL.
- **Email**: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_USE_TLS, SMTP_DEFAULT_FROM.
- **Parkpe (voucher email)**: SMTP_HOST_Parkpe, SMTP_PORT_Parkpe, SMTP_USER_Parkpe, SMTP_PASSWORD_Parkpe, SMTP_DEFAULT_FROM_Parkpe (optional).

Optional (feature-specific): CASHFREE_* (verification), LEGALITY_* (Leegality), CASHFREE_PG_* (payment gateway), MOBIKWIK_BBPS_* (Mobikwik BBPS), EURONET_BBPS_* (Euronet BBPS), PAYPOINT_AEPS_*, PAYPOINT_DMT_*, S3_*, SENTRY_*, CORS_ALLOWED_ORIGINS, GOOGLE_OAUTH_*, FACEBOOK_OAUTH_*, APPLE_OAUTH_*.

### Dev vs UAT vs Production

- **Development**: DEBUG=True allowed; APP_ENV=development; CORS and ALLOWED_HOSTS per dev; Celery pool `solo` on macOS to avoid SIGSEGV.
- **UAT/Staging**: DEBUG=False; APP_ENV=staging; vendor configs point to UAT (e.g. MOBIKWIK_BBPS_ENVIRONMENT=UAT, PAYPOINT_AEPS_ENVIRONMENT=UAT); CASHFREE_PG_ENVIRONMENT=SANDBOX if applicable.
- **Production**: DEBUG must be False (Pydantic validator); APP_ENV=production; SECURE_* and HSTS enabled; vendor envs set to PRODUCTION where applicable; strong SECRET_KEY and keys.

---

## 12. Deployment Flow

### How the Project Is Deployed

- Not automated in repo; typically: clone, venv, install deps, configure env, DB migrate, static collect, run gunicorn/uwsgi and Celery worker (and optionally Beat). Frontend (Angular) in `frontend-space/` is separate build if used.

### Build Steps

1. Python 3.12+ venv: `python -m venv .venv`; activate.
2. Install: `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set variables.
4. Static (if serving from Django): `python manage.py collectstatic --noinput`.
5. Frontend (optional): In `frontend-space/`, `npm ci` and build (e.g. `ng build`) for Parkpe/Payswap apps; serve via Django or separate server.

### Migration Steps

1. Backup DB.
2. `python manage.py migrate` (run all portal/api migrations).
3. If new roles: `python manage.py setup_roles` (or equivalent).
4. Restart app and Celery workers after code/config changes.

---

## 13. Known Limitations & Assumptions

- **Hardcoded / config**: Vendor selection (e.g. BBPS) by param or config; some defaults (e.g. rate limits, retry counts) in code. Partner pricing fallback (e.g. voucher amount as charge when no ResellerPartnerPricing) is implicit.
- **Missing validations**: Not all endpoints document idempotency keys; file upload type/size limits may vary by view; some optional KYC fields not strictly validated.
- **MFA**: Enforced only for certain roles; TOTP secret stored encrypted but key rotation not documented.
- **Sentry**: Disabled in settings; re-enable when dependency conflict with cashfree_pg is resolved.
- **Celery Beat**: No beat schedule in code; periodic tasks (log cleanup, voucher OTP cleanup, PIN unlock) must be scheduled manually or via Beat config.
- **Frontend**: Angular apps in `frontend-space/` are separate; no single “app” document describing full user flows for Parkpe/Payswap landing.
- **Assumptions**: PostgreSQL and Redis available; single-tenant deployment; partner wallet in same DB; external vendors’ availability and correctness of their APIs assumed.
- **Future scope**: JWT for mobile/external clients; more idempotency keys; full audit export; additional vendors and regions.

---

*Document generated from codebase analysis. For exact request/response fields, see serializers in `api/v1/` and `api/v2/`, and OpenAPI at `/api/schema/`.*
