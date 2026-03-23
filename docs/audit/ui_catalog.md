# Phase 0 Audit — Step 3: UI Screen Catalog

**Read-only audit. No code changes.**

**Note:** Admin dashboard, Super Admin, Analytics, and ParkPe App Management have been removed; their URLs redirect to /dashboard/. See [REMOVED_FEATURES.md](../REMOVED_FEATURES.md).

---

## 1. Portal (Django templates)

Templates live under `portal/templates/` (base.html, portal/*). Views resolve from portal/urls.py and portal/views (including governance, super_admin).

### 1.1 Auth

| Screen | Route | View | Data source |
|--------|--------|------|-------------|
| Landing | `/` | LandingPageView | — |
| Sign in | `/signin/` | SignInView | Session, User |
| Sign up / OTP | `/signup/`, `/signup/otp/` | SignUpView | Session, User, OTP |
| MFA setup / verify | `/mfa/setup/`, `/mfa/verify/` | MFASetupView, MFAVerifyView | User (TOTP) |
| Forgot password | `/forgot-password/` | ForgotPasswordView | Email |
| Set PIN / Unlock | `/auth/set-pin/`, `/auth/unlock-with-pin/` | SetPinView, UnlockWithPinView | Session, User |

### 1.2 Dashboards (role-based)

| Screen | Route | View | Data source |
|--------|--------|------|-------------|
| Dashboard (generic) | `/dashboard/` | DashboardView | Role redirect |
| Admin dashboard | `/dashboard/admin/` | Removed; redirects to /dashboard/ | — |
| Employee / Super / Distributor / Retailer / Customer / Vendor | `/dashboard/employee/`, etc. | *DashboardView | Role-specific |
| Governance dashboard | `/dashboard/governance/` | GovernanceDashboardView | Health, jobs |
| Control tower | `/dashboard/control-tower/` | ControlTowerView | get_health_summary, SystemJobStatus |
| System status | `/dashboard/system-status/` | SystemStatusView | SystemJobStatus, health |
| Super Admin overview | `/dashboard/super-admin/`, `/super-admin/` | Removed; redirects to /dashboard/ | — |
| Analytics | `/analytics/` | Removed; redirects to /dashboard/ | — |

### 1.3 Super Admin (removed)

All Super Admin screens have been removed; URLs redirect to /dashboard/. See REMOVED_FEATURES.md.

### 1.4 Governance (portal)

| Screen | Route | View | Data source |
|--------|--------|------|-------------|
| APIs, Partners, Emergency, Audit, Settings, System status | `/dashboard/governance/apis/`, partners, emergency, audit, settings, system-status | GovernanceAPIsView, etc. | APIRegistry, partners, kill switch, ControlAuditLog |

### 1.5 Partner / Reseller (portal)

| Screen | Route | View | Data source |
|--------|--------|------|-------------|
| Reseller dashboard | `/reseller/` | ResellerDashboardView | ResellerPartner, APIKey |
| Partner dashboard (alias) | `/partners/` | ResellerDashboardView | Same |
| Partner console | `/partner/dashboard/` | PartnerDashboardView | Partner API keys, usage |
| Admin partners (list, onboard, detail, pricing, settlement, vendors) | `/admin/partners/`... | AdminResellerPartner*View | ResellerPartner, Wallet, settlements |

### 1.6 Vouchers / VoucherX (portal)

| Screen | Route | View | Data source |
|--------|--------|------|-------------|
| Voucher brands, clients, batches, issue, list, detail, reports | `/vouchers/*` | BrandListView, VoucherListView, etc. | Portal voucher models |
| VoucherX dashboard, balance, debit, tabs, wizard, onboard | `/voucherx/*` | VoucherXDashboardView, etc. | VoucherX / API |

### 1.7 ParkPe (portal backend UI)

| Screen | Route | View | Data source |
|--------|--------|------|-------------|
| App management | `/parkpe/app-management/` | Removed; redirects to /dashboard/ | — |
| Connect dashboard | `/parkpe/connect/` | ParkPeConnectDashboardView | Connect stats |

### 1.8 Services, API registry, Logs, Tickets, Profile, Users, KYC, Wallet, Permissions

| Area | Routes | Data source |
|------|--------|-------------|
| Services | `/services/`, `/services/<id>/vendor/`, bbps-test, etc. | Service, ApiVendor |
| API registry | `/dashboard/admin/api-registry/` | APIRegistry, APIProduct, APILog |
| Logs | `/logs/`, `/logs/<pk>/` | Log models |
| Tickets | `/tickets/` | Ticket |
| Profile, users, KYC, wallet, permissions | `/profile/`, `/users/`, `/kyc/`, `/wallet/`, `/permissions/` | User, Profile, KYC, Wallet |

---

## 2. Angular — ParkPe

Base path: app served from frontend-space/projects/parkpe (e.g. `/` or configured base).

| Screen | Route | Component | Data source (API) |
|--------|--------|-----------|-------------------|
| Home | `/home` | HomeComponent | — |
| Connect scan (public) | `/connect/scan/:qrCode` | ConnectScanResultComponent | — |
| Login, Register, Forgot password | `/auth/login`, register, forgot-password | LoginComponent, RegisterComponent, ForgotPasswordComponent | `/api/auth/*` |
| Dashboard | `/dashboard` | DashboardComponent | `/api/dashboard/summary` etc. |
| Connect (info, scan, chats, vehicles, app) | `/connect/*` | ConnectLanding, ConnectScan, ConnectChatsShell, ConnectVehiclesShell, etc. | `/api/connect/*` |
| Parking | `/parking` | (parking.routes) | — |
| BBPS | `/bbps` | BBPSInternalComponent | `/api/bbps/*` |
| Fastag, Challan | `/fastag`, `/challan` | feature routes | — |
| Payment (checkout, status, callback, receipt, history, reports) | `/payment/*` | PaymentPageComponent, PaymentStatusComponent, etc. | `/api/payment/*` |
| Vouchers | `/vouchers` | (voucher.routes) | `/api/voucher/*` |
| Profile | `/profile` | (profile.routes) | `/api/auth/profile` |
| Settings | `/settings` | SettingsComponent | — |

---

## 3. Angular — Payswap Governance

Standalone app (payswap-governance): dashboard, apis, partners, emergency, audit, settings.

| Screen | Route | Component | Data source |
|--------|--------|-----------|-------------|
| Login | `login` | LoginComponent | — |
| Dashboard | `dashboard` | DashboardComponent | API control/dashboard |
| APIs | `apis` | ControlComponent | `/api/control/apis` |
| Partners | `partners` | PartnersComponent | `/api/control/partners` |
| Emergency | `emergency` | EmergencyComponent | Kill switch, etc. |
| Audit | `audit` | AuditComponent | `/api/control/audit-log` |
| Settings | `settings` | SettingsComponent | — |

---

## 4. Duplicate / overlapping screens (findings)

- **Partner dashboards:** Portal has (1) `/reseller/` and `/partners/` (same ResellerDashboardView), (2) `/partner/dashboard/` (PartnerDashboardView), (3) Admin `/admin/partners/` (list, detail, etc.), (4) Super Admin `super-admin/partners/`, (5) Governance `dashboard/governance/partners/`, (6) Angular payswap-governance `partners`. Multiple UIs for “partner” concepts.
- **Billing / finance:** Portal admin partner pricing and settlement (`/admin/partners/<id>/pricing/`, settlement); Super Admin “Finance” section; Enterprise API reconciliation/settlement; no single “billing” app — spread across admin, super admin, API.
- **Settings:** Portal `/settings/` (user settings); Super Admin “API & Access” / “Security”; Governance `dashboard/governance/settings/`; Angular ParkPe `settings`; Angular payswap-governance `settings`. Multiple “settings” entry points.
- **Kill switch / emergency:** Governance UI (`dashboard/governance/emergency/`) and Super Admin Emergency (`super-admin/emergency/`); both can toggle kill switch and have overlapping purpose.
- **Dashboard “overview”:** Role dashboards (admin, employee, super, etc.), Governance dashboard, Control tower, System status, Super Admin overview, Angular ParkPe dashboard, Angular governance dashboard — many “dashboard” or “overview” screens.

---

*End of Step 3 — UI Screen Catalog.*
