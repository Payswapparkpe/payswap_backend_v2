# Phase 0 Audit — Step 10: End-to-End Flow Trace

**Read-only audit. No code changes.**

---

## Flow summary table

| Flow | From | To | Key files / notes |
|------|------|-----|-------------------|
| **ParkPe Connect** | UI (Angular ParkPe or Portal parkpe/connect) | API `/api/connect/*` (vehicles, RC, QR, call, chat, scanner, report) | **Entry:** ParkPe `connect.routes.ts` → ConnectService; Portal `ParkPeConnectDashboardView`. **API:** `api/connect/urls.py`, `api/connect/views/`, `api/connect/rc_visibility.py`. **Vendor:** Cashfree vehicle RC, Kaleyra call; DB: Vehicle, VehicleRCData, ConnectThread, ConnectMessage. **Exit:** JSON response, DB writes. |
| **BBPS** | UI (Angular ParkPe BBPS or Portal services BBPS test) | API `/api/bbps/*` or `/api/v2/` BBPS | **Entry:** ParkPe bbps feature, Portal `bbps_test_*` views. **API:** `api/bbps_parkpe/urls.py`, `api/v2/bbps_views.py`. **Vendor:** Mobikwik, Euronet. **Exit:** Bill fetch, pay, status; DB/cache. |
| **Billing** | Cron or Super Admin System Control | `run_billing_cycle` / `generate_invoices` → billing_service | **Entry:** Super Admin System Control run job, or POST `/internal/run-job/` (run_billing_cycle). **Commands:** `portal/management/commands/run_billing_cycle.py`, `generate_invoices.py`. **Service:** `portal/services/billing_service.py` (run_billing_cycle, generate_partner_documents). **Exit:** ResellerPartnerSettlement, PDF invoices (media/partner_invoices/), optional email. |
| **Partner onboarding** | Admin Portal or Super Admin | DB, API keys | **Entry:** `/admin/partners/onboard/` (AdminResellerPartnerOnboardView), or Super Admin partners; `create_internal_api_keys`, `ensure_parkpe_partner`, `migrate_parkpe_partner` commands. **Services:** api_key_service, reseller_service, partner_vendor_service. **Exit:** ResellerPartner, APIKey, PartnerVendorAssignment. |
| **Governance** | UI (Control Tower, Super Admin, Governance dashboard) or API | Redis (kill switch), DB (FeatureFlag, ControlAuditLog) | **Entry:** `/dashboard/control-tower/`, `/dashboard/governance/emergency/`, `/super-admin/emergency/`, `/api/control/*` (kill-switch, feature-flags, audit-log). **Services:** control_tower_health, control_audit_service; middleware reads GOV_KILL_SWITCH_CACHE_KEY, is_feature_enabled. **Exit:** Cache key set/unset, ControlAuditLog entry, 503 when kill on. |
| **Super Admin job run** | UI (System Control) or POST `/internal/run-job/` | command_runner_service / Celery | **Entry:** Super Admin System Control “Run job” (SuperAdminRunJobView) or InternalRunJobView. **Services:** job_run_service.run_command_with_logging → command_runner_service (ALLOWED_COMMANDS), or Celery run_management_command_async. **Exit:** SystemJobRun record, ControlAuditLog, command stdout/stderr. |
| **ParkPe Auth** | Angular ParkPe login/register | API `/api/auth/*` (login, OTP, register, profile) | **Entry:** ParkPe auth routes → AuthService → real-api.service. **API:** `api/auth_parkpe/urls.py`, `api/auth_parkpe/views.py`. **Exit:** JWT, session; User, Profile. |
| **ParkPe Payment** | Angular ParkPe payment flow | API `/api/payment/*` (gateways, create-order, verify, webhook) | **Entry:** ParkPe payment routes → PaymentGatewayService. **API:** `api/parkpe_api/payment_urls.py`, payment_views. **Vendor:** Cashfree PG. **Exit:** ParkPePaymentOrder, redirect/callback, receipt. |
| **ParkPe Voucher** | Angular ParkPe vouchers | API `/api/voucher/*` (list, detail, reveal-pin) | **Entry:** ParkPe voucher routes → VoucherService. **API:** `api/parkpe_api/voucher_urls.py`. **Bridge:** parkpe_voucherx_bridge, voucher_service. **Exit:** Voucher list/detail, PIN reveal. |
| **Enterprise reporting** | API client (token) | `/api/enterprise/reconciliation/`, settlement, compliance | **Entry:** Enterprise API with auth. **API:** `api/enterprise/urls.py`, enterprise views. **Exit:** Read-only audited data (reconciliation, settlement, compliance). |

---

## Short narrative per flow

- **ParkPe Connect:** User scans QR or opens Connect; Angular calls `/api/connect/vehicles/`, RC fetch, call token, chat threads. Portal can view Connect dashboard at `/parkpe/connect/`. External vendors: Cashfree (RC), Kaleyra (calls). Data in portal_connect_* and ParkPe app config.

- **BBPS:** User selects operator, fetches bill, pays. ParkPe uses `/api/bbps/*` or v2 BBPS views. Portal has BBPS test pages under services. Vendors: Mobikwik, Euronet. Operators loaded via load_bbps_operators command.

- **Billing:** Scheduled or manual. run_billing_cycle creates settlements and can generate invoices; generate_invoices uses same billing_service. Output: ResellerPartnerSettlement rows, HTML/PDF in media/partner_invoices/. Optional email. No dedicated “billing UI” other than admin partner settlement and Super Admin Finance.

- **Partner onboarding:** Admin creates partner at /admin/partners/onboard/; commands create internal keys and assign vendors. API keys stored hashed; partner can use Partner Console (/partner/dashboard/) and reseller views (/reseller/).

- **Governance:** Kill switch and feature flags control API availability. Toggled from Governance Emergency or Super Admin Emergency; state in Redis (GOV_KILL_SWITCH_CACHE_KEY) and env (API_GOVERNANCE_KILL_SWITCH). Control Tower and Health Center consume control_tower_health.get_health_summary; audit in ControlAuditLog.

- **Super Admin job run:** Allowed commands (e.g. audit_partners, run_billing_cycle, compute_sla) run via System Control “Run job” or /internal/run-job/. job_run_service logs to SystemJobRun; command_runner_service runs sync or enqueues Celery. Audit trail in ControlAuditLog.

- **ParkPe Auth / Payment / Voucher:** Standard SPA → REST flows. Auth yields JWT; payment goes through Cashfree; voucher uses VoucherX bridge and portal voucher models. Key files: auth_parkpe/views, parkpe_api payment_urls/voucher_urls, frontend-space/projects/parkpe services.

- **Enterprise:** Read-only APIs for reconciliation, settlement, compliance; used by external systems with appropriate tokens; no UI in this repo.

---

*End of Step 10 — Flow Trace.*
