# Phase 0 Audit — Step 2: URL & View Inventory

**Read-only audit. No code changes.**

---

## 1. Auth

| URL / Prefix | View / Endpoint | Location | Notes |
|--------------|-----------------|----------|--------|
| `/signin/` | SignInView | portal.views | Portal login |
| `/signup/`, `/signup/otp/` | SignUpView | portal.views | Portal signup |
| `/logout/` | sign_out_view | portal.views | |
| `/mfa/setup/`, `/mfa/verify/`, `/mfa/resend-otp/` | MFASetupView, MFAVerifyView, resend_otp_view | portal.views | |
| `/forgot-password/`, `/password/reset/...`, `/password/change/` | ForgotPasswordView, PasswordResetView, PasswordChangeView | portal.views | |
| `/auth/set-pin/`, `/auth/unlock-with-pin/`, `/auth/lock/` | SetPinView, UnlockWithPinView, lock_screen_view | portal.views | |
| `/api/auth/login`, `otp/request`, `otp/verify`, `register/*`, `profile`, `logout`, `forgot-password` | AuthLoginView, AuthOTPRequestView, etc. | api.auth_parkpe.views | ParkPe Angular (JWT) |
| `/api/v1/auth/token/`, `/api/v1/auth/token/refresh/` | TokenObtainPairView, TokenRefreshView | api.v1.urls | JWT for API consumers |

**Angular (parkpe):** `auth/login`, `auth/register`, `auth/forgot-password` (guestGuard).

---

## 2. Dashboard

| URL / Prefix | View | Location | Notes |
|--------------|------|----------|--------|
| `/dashboard/` | DashboardView | portal.views | Role-based redirect |
| `/dashboard/admin/` | RedirectView | portal.urls | Removed; redirects to /dashboard/. See docs/REMOVED_FEATURES.md |
| `/dashboard/employee/`, `/dashboard/super/`, `/dashboard/distributor/`, etc. | *DashboardView per role | portal.views.dashboard_views | |
| `/dashboard/governance/` | include(governance.urls) | portal.views.governance | Governance dashboard, control-tower, apis, partners, emergency, audit, settings, system-status |
| `/dashboard/super-admin/`, `/super-admin/` | RedirectView | portal.urls | Removed; redirects to /dashboard/. See docs/REMOVED_FEATURES.md |
| `/dashboard/system-status/` | SystemStatusView | portal.views.governance.system_status | |
| `/dashboard/control-tower/` | ControlTowerView | portal.views.governance.control_tower | |
| `/dashboard/admin/api-registry/` | APIProductListView, APIRegistryListView, APIRegistryToggleView, APILogListView | portal.views | Admin API registry |
| `/api/dashboard/overview`, `technical`, `financial`, `operations`, `business` | GovernanceDashboard*View | api.governance.views_dashboard | JWT + RBAC |
| `/api/dashboard/summary`, `pincode` | DashboardSummaryView, PincodeLookupView | api.parkpe_api.urls | ParkPe |

**Angular (parkpe):** `dashboard` (DashboardComponent), `home`.

---

## 3. Partner

| URL / Prefix | View | Location | Notes |
|--------------|------|----------|--------|
| `/admin/partners/` | AdminResellerPartnerDashboardView, list, onboard, detail, pricing, settlement, vendors, etc. | portal.views (core.urls) | Admin partner management |
| `/reseller/` | ResellerDashboardView, onboarding, api-keys, usage-stats | portal.views | Reseller self-service |
| `/partners/` | ResellerDashboardView (same as reseller) | portal.views | **Same view as reseller** — alias |
| `/partner/dashboard/` | PartnerDashboardView | portal.views | Partner console |
| `/partner/invoice/<doc_type>/<period>/` | PartnerInvoiceDownloadView | portal.views | |
| `/api/control/partners`, `partners/<pk>/subscriptions`, `partners/<pk>/limits` | ControlPartnersListView, ControlPartnerSubscriptionsView, ControlPartnerLimitsView | api.governance.views_control | Governance API |
| `/api/v1/control/partners` | ControlPartnersListView | api.v1.views | **Overlap:** v1 control vs api/control |

---

## 4. Billing / Finance / Settlement

| URL / Prefix | View | Location | Notes |
|--------------|------|----------|--------|
| `/admin/partners/<id>/pricing/` | AdminResellerPartnerPricingView | portal.views | |
| `/admin/partners/<id>/settlement/` | AdminResellerPartnerSettlementView | portal.views | |
| `admin/partners/settlement/<id>/process/` | AdminResellerPartnerSettlementProcessView | portal.views | |
| `/api/enterprise/reconciliation/`, `/settlement/`, `/compliance/` | EnterpriseReconciliationView, EnterpriseSettlementView, EnterpriseComplianceView | api.enterprise.views | Enterprise (read-only, audited) |

---

## 5. Governance

| URL / Prefix | View | Location | Notes |
|--------------|------|----------|--------|
| `/dashboard/governance/` | GovernanceDashboardView | portal.views.governance | |
| `/dashboard/governance/control-tower/` | ControlTowerView | portal.views.governance | |
| `/dashboard/governance/apis/`, `apis/<pk>/toggle/` | GovernanceAPIsView, GovernanceAPIToggleView | portal.views.governance | |
| `/dashboard/governance/partners/` | GovernancePartnersView | portal.views.governance | |
| `/dashboard/governance/emergency/`, `emergency/kill-switch/` | GovernanceEmergencyView, GovernanceKillSwitchPostView | portal.views.governance | **Kill switch** (UI) |
| `/dashboard/governance/audit/`, `settings/`, `system-status/` | GovernanceAuditView, GovernanceSettingsView, SystemStatusView | portal.views.governance | |
| `/api/control/apis`, `apis/<pk>/toggle`, `partners`, `kill-switch`, `feature-flags`, `vendor-health`, `audit-log` | Control*View | api.governance.views_control | Governance REST API |
| `/api/v1/control/overview`, `control/apis`, `control/partners` | ControlOverviewView, ControlAPIsListView, ControlPartnersListView | api.v1.views | **Deprecated in favour of api/control/** (per api/urls.py comment) |

---

## 6. Super Admin

| URL / Prefix | View | Location | Notes |
|--------------|------|----------|--------|
| `/dashboard/super-admin/`, `/super-admin/` | SuperAdminOverviewView, partners, api_access, finance, security, system, system_control, health_center, job_history, alerts, compliance, growth, emergency, reports | portal.views.super_admin | **Duplicate mount** — namespace 'super_admin' not unique (Django warning) |
| `/dashboard/super-admin/system/run-command/`, `/super-admin/system-control/run/` | SuperAdminRunCommandView, SuperAdminRunJobView | portal.views.super_admin | Run command (two entry points: system vs system_control) |
| `/dashboard/super-admin/emergency/kill-switch/`, `cache-reset/` | SuperAdminKillSwitchPostView, SuperAdminCacheResetView | portal.views.super_admin | **Kill switch / cache** — overlap with governance emergency |

---

## 7. Operations / Internal / Health

| URL / Prefix | View | Location | Notes |
|--------------|------|----------|--------|
| `/internal/health/` | InternalHealthView | api.internal.views | Ops health (DB, Redis, kill_switch) |
| `/internal/run-job/` | InternalRunJobView | api.internal.views | Super Admin run command (session + CSRF) |
| `/api/v1/health/` | HealthCheckView | api.v1.views | Internal API health |
| `/api/v2/health/` | HealthCheckView | api.v2.views | External API health |

---

## 8. API (ParkPe / External)

| Prefix | Purpose | Location |
|--------|---------|----------|
| `/api/auth/` | Login, OTP, register, profile, logout | api.auth_parkpe |
| `/api/connect/` | Vehicles, call, scanner, chat, report, admin/stats | api.connect |
| `/api/bbps/` | Categories, operators, fetch-bill, pay, pay-cart, favorites, saved-bills | api.bbps_parkpe |
| `/api/payment/` | Gateways, create-order, verify, webhook, transactions, orders, voucher-statement | api.parkpe_api.payment_urls |
| `/api/voucher/` | vouchers list/detail, reveal-pin | api.parkpe_api.voucher_urls |
| `/api/v2/*` | Voucher, KYC, Payment, SMS, BBPS, AEPS, DMT, vendor/service flows | api.v2 (many views) |

---

## 9. Analytics

| URL | View | Location |
|-----|------|----------|
| `/analytics/` | RedirectView | portal.urls — Removed; redirects to /dashboard/. See docs/REMOVED_FEATURES.md |

---

## 10. Angular routes (ParkPe)

| Route | Component / Module | Notes |
|-------|--------------------|--------|
| `''` | redirect to `/home` | |
| `home` | HomeComponent | |
| `connect/scan/:qrCode` | ConnectScanResultComponent | Public, no layout |
| `auth/login`, `auth/register`, `auth/forgot-password` | Login, Register, ForgotPassword | guestGuard |
| `dashboard` | DashboardComponent | authGuard, AppLayout |
| `connect` | loadChildren connect.routes | |
| `parking`, `bbps`, `fastag`, `challan` | feature routes | |
| `payment`, `vouchers`, `profile`, `settings` | feature routes / SettingsComponent | |

---

## Findings (no solutions)

- **Multiple URLs same job:** `/partners/` and `/reseller/` both use ResellerDashboardView. Super Admin mounted at `/dashboard/super-admin/` and `/super-admin/` (same app, two mounts).
- **Deprecated but active:** `/api/v1/control/*` documented as deprecated in favour of `/api/control/` but still present.
- **Hidden / admin-only:** `/admin/partners/*`, `/dashboard/admin/api-registry/*`, `/dashboard/governance/*`, `/dashboard/super-admin/` and `/super-admin/*`, `/internal/run-job/` — all require staff/super_admin or equivalent.
- **Kill switch in two places:** Governance emergency (UI + API) and Super Admin emergency (UI). Both can toggle; audit trail may differ.
- **Control tower overlap:** Portal pages `dashboard/governance/control-tower/` and `dashboard/system-status/`; API `api/control/*` and dashboard `api/dashboard/overview` etc. — multiple ways to see governance state.

---

*End of Step 2 — URL & View Inventory.*
