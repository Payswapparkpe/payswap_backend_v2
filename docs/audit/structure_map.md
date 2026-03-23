# Phase 0 Audit — Step 1: Repo Structure Map

**Read-only audit. No code changes.**

---

## 1. Repo root

| Directory | Purpose |
|-----------|---------|
| `api/` | Django app: REST API (v1, v2, auth, connect, bbps, payment, voucher, governance, enterprise, internal) |
| `portal/` | Django app: Web portal (views, templates, services, management commands) |
| `core/` | Django project: settings, urls, celery, config, wsgi/asgi |
| `frontend-space/` | Angular workspace: projects parkpe, payswap, payswap-governance, shared |
| `scripts/` | Standalone scripts (pre_deploy_check.sh, fetch_carwale_images.py, send_parkpe_test_email.py, start_lan.sh) |
| `docs/` | Documentation (markdown) |
| `api_management/` | Django app: API registry, control audit, system jobs, feature flags (referenced in core but sibling to api/portal) |

---

## 2. Django apps and modules

**INSTALLED_APPS (core/settings.py):**  
`django.contrib.*`, `rest_framework`, `drf_spectacular`, `corsheaders`, `django_celery_beat`, `django_celery_results`, `django_filters`, `simple_history`, `allauth.*`, **api**, **portal** (PortalConfig), **api_management** (ApiManagementConfig).

**api/**  
- Subpackages: `auth_parkpe`, `bbps_parkpe`, `connect`, `enterprise`, `governance`, `internal`, `middleware`, `mixins`, `parkpe_api`, `tests`, `utils`, `v1`, `v2`.  
- Root: `urls.py`, `urls_dashboard.py`, `views.py`, `models.py`, `admin.py`, `parkpe_logging.py`, `throttling.py`.

**portal/**  
- Subpackages: `management/commands/`, `models/` (e.g. _monolith.py), `services/`, `templates/`, `views/` (governance, super_admin, etc.), `tasks/`.  
- Root: `urls.py`, `views.py` (and views in legacy.py, dashboard_views, etc.).

**api_management/**  
- Subpackages: `management/commands/`, `migrations/`, `services/`.  
- Root: `models.py`, `admin.py`, `urls.py` (if any), `control_audit_service.py`, tasks.

---

## 3. URL routers tree

**Entry: core/urls.py**

- `admin/partners/` → inline list (portal_views: AdminResellerPartner*, VendorManagement*, ServiceCatalog*, etc.)
- `admin/` → Django admin
- `api/` → include(api.urls)
- `internal/` → include(api.internal.urls) — health, run-job
- `api/schema/`, `api/schema/swagger-ui/`, `api/schema/redoc/` → Spectacular
- `accounts/` → allauth
- `""` → include(portal.urls)

**portal/urls.py** (major groups)

- Auth: ``, `signin/`, `signup/`, `logout/`, `mfa/*`, `auth/*`, `forgot-password/`, `password/*`
- Dashboard: `dashboard/`, `dashboard/admin/`, `dashboard/employee/`, `dashboard/super/`, etc.
- Profile, settings, users, kyc, wallet, permissions, roles
- Logs, tickets, api-docs, api-explorer
- Services (long list: services/, services/api-vendors/, services/<id>/vendor/, bbps-test/, etc.)
- Vouchers: vouchers/brands/, vouchers/clients/, vouchers/batches/, vouchers/issue/, voucherx/*
- Reseller/partner: reseller/*, partners/, partner/dashboard/, partner/invoice/
- ParkPe: parkpe/app-management/, parkpe/connect/
- API registry: dashboard/admin/api-registry/*
- Governance: `dashboard/governance/` → include(portal.views.governance.urls)
- Super Admin: `dashboard/super-admin/` and `super-admin/` → include(portal.views.super_admin.urls)
- System status: `dashboard/system-status/`, `dashboard/control-tower/`
- Analytics: `analytics/`

**api/urls.py**

- `v1/` → api.v1.urls
- `v2/` → api.v2.urls
- `enterprise/` → api.enterprise.urls
- `control/` → api.governance.urls_control
- `dashboard/` → api.urls_dashboard
- `auth/` → api.auth_parkpe.urls
- `connect/` → api.connect.urls
- `bbps/` → api.bbps_parkpe.urls
- `payment/` → api.parkpe_api.payment_urls
- `voucher/` → api.parkpe_api.voucher_urls

**Sub-urls (included)**

- portal.views.governance.urls: dashboard, control-tower, apis, partners, emergency, audit, settings, system-status
- portal.views.super_admin.urls: overview, partners, api-access, finance, security, system, system-control, health-center, job-history, alerts, compliance, growth, emergency, reports
- api.internal.urls: health/, run-job/
- api.v1.urls, api.v2.urls, api.enterprise.urls, api.governance.urls_control, api.urls_dashboard, api.auth_parkpe.urls, api.connect.urls, api.bbps_parkpe.urls, api.parkpe_api (payment_urls, voucher_urls)

---

## 4. Portal templates layout

**Base:** `portal/templates/base.html`, `portal/templates/portal/partials/sidebar_menu.html`

**Feature groups (under portal/templates/portal/):**

- **super_admin/** — base, overview, partners, partner_detail, api_access, finance, security, system, system_control, health_center, job_history, alerts, compliance, growth, emergency, reports
- **governance/** — dashboard, system_status, control_tower, apis, partners, emergency, audit, settings
- **analytics/** — dashboard
- **partner/** — dashboard
- **api_registry/** — list, product_list, log_list
- **parkpe/** — connect_dashboard, app_management, gateway_config_form, service_config_form
- **dashboard/** — admin, super, distributor, etc.
- **admin/** — reseller_partners (dashboard, list, detail, onboard, pricing, settlement, reports), partner_vendor_assignment, vendor_management_dashboard, service_catalog, assign_service_vendor_to_partners
- **services/** — list, detail, api_vendor_*, vendor_detail, *vendor_detail (kaleyra, cashfree, mobikwik, etc.)
- **reseller/** — dashboard, onboarding, api_keys, usage_stats
- **vouchers/** — brands, clients, batches, issuance, vouchers (list, detail, search), reports
- **voucherx/** — dashboard, balance_check, debit, tabbed, wizard_issue, admin_onboard
- **auth/** — signin, set_pin, unlock_with_pin
- **emails/** — voucher_purchase_confirmation, parkpe_welcome, voucher_delivery
- **profile/**, **users/**, **wallet/**, **tickets/**, **permissions/**, **kyc/**, etc.

Templates total: 150+ HTML files under portal/templates.

---

## 5. Angular projects and modules

**frontend-space/angular.json projects:**  
`payswap`, `parkpe`, `payswap-governance`, `shared` (library).

**Entry points:**  
- payswap: `projects/payswap/src/main.ts`  
- parkpe: `projects/parkpe/src/main.ts`  
- payswap-governance: (separate app)

**Routing files found:**

- `payswap-governance/src/app/app.routes.ts`
- `payswap/src/app/app.routes.ts`
- `parkpe/src/app/app.routes.ts`
- `parkpe/src/app/features/payment/payment.routes.ts`
- `parkpe/src/app/features/fastag/fastag.routes.ts`
- `parkpe/src/app/features/challan/challan.routes.ts`
- `parkpe/src/app/features/connect/connect.routes.ts`
- `parkpe/src/app/features/voucher/voucher.routes.ts`
- `parkpe/src/app/features/bbps/bbps.routes.ts`
- `parkpe/src/app/features/parking/parking.routes.ts`
- `parkpe/src/app/features/profile/profile.routes.ts`

**ParkPe app structure:**  
`src/app/` with features: auth, bbps, challan, connect, dashboard, fastag, home, payment, profile, voucher, parking, etc. (components, services, models per feature).

---

## 6. Entry points summary

| Type | Entry | Notes |
|------|--------|------|
| Django | `manage.py` | WSGI/ASGI via core (core.settings, core.urls) |
| Django URLs | `core/urls.py` | Mounts api/, internal/, portal/ |
| Portal | `portal/urls.py` | Mounted at "" and contains 200+ path entries and includes |
| API | `api/urls.py` | Mounted at api/; versioned and feature includes |
| Angular parkpe | `frontend-space/projects/parkpe/src/main.ts` | Bootstrap; app.routes.ts + feature routes |
| Angular payswap | `frontend-space/projects/payswap/src/main.ts` | Bootstrap; app.routes.ts |
| Angular governance | `frontend-space/projects/payswap-governance` | Separate app |
| Scripts | `scripts/pre_deploy_check.sh`, `scripts/*.py` | Standalone runnables |

---

*End of Step 1 — Structure Map.*
