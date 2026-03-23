# Phase 0 Audit — Step 7: Sidebar & Navigation Audit

**Read-only audit. No code changes.**

**Note:** Several items below (API Docs, API Explorer, Super Admin, ParkPe App Management, Back to Admin) have been removed; their URLs redirect to /dashboard/. See [REMOVED_FEATURES.md](../REMOVED_FEATURES.md).

---

## 1. Portal nav tree (Django)

### 1.1 Main sidebar (portal/templates/portal/partials/sidebar_menu.html)

Rendered in base shell; links use `{% url 'name' %}`. Active state by `request.path` (prefix or exact).

| Label | URL name | Resolves to (from portal + core urls) |
|-------|----------|----------------------------------------|
| Dashboard | dashboard | /dashboard/ |
| VoucherX | voucherx_dashboard | /voucherx/ (super, admin, staff) |
| Users | user_list | /users/ (permission: portal.view_user) |
| Profile | profile | /profile/ |
| Settings | settings | /settings/ |
| KYC | kyc_list | /kyc/ (portal.view_kyc) |
| Wallet | wallet | /wallet/ (portal.view_wallet) |
| Permissions | permissions | /permissions/ (portal.view_userpermission) |
| Logs | log_list | /logs/ (super, admin, staff) |
| API Docs | api_docs | Removed; redirects to /dashboard/ |
| API Explorer (Postman) | api_explorer | Removed; redirects to /dashboard/ |
| Services | services_list | /services/ |
| Partner Management | admin_reseller_partner_dashboard | /admin/partners/ |
| Control Tower | governance:dashboard | /dashboard/governance/ |
| ParkPe App Management | parkpe_app_management | Removed; redirects to /dashboard/ |
| Tickets | ticket_list | /tickets/ |

All above URL names exist in portal/urls.py or core/urls.py; no dead links detected from names.

**Note:** Active for Partner Management uses `'/admin/partners/' in request.path` — matches /admin/partners/ and children (e.g. /admin/partners/123/).

### 1.2 Governance inner nav (repeated in governance/*.html)

Tabs on each governance page (dashboard, apis, partners, emergency, audit, settings, control_tower, system_status):

| Label | URL name | Path |
|-------|----------|------|
| Overview | governance:dashboard | /dashboard/governance/ |
| APIs | governance:apis | (under governance include) |
| Partners | governance:partners | (under governance include) |
| Emergency | governance:emergency | (under governance include) |
| Audit | governance:audit | (under governance include) |
| Settings | governance:settings | (under governance include) |
| Control Tower | governance:control_tower | /dashboard/control-tower/ (or governance prefix) |
| System status | governance:system_status | /dashboard/system-status/ |
| Super Admin | super_admin:overview | /dashboard/super-admin/ (from include) |
| Back to Admin | dashboard_admin | Removed; redirects to /dashboard/ |

Governance URLs are under `path('dashboard/governance/', include('portal.views.governance.urls'))`; control_tower and system_status are also exposed at dashboard/control-tower/ and dashboard/system-status/ (portal/urls.py). So “Control Tower” and “System status” in governance nav may point to same views via governance include — need not be dead.

### 1.3 Super Admin sidebar (removed)

Super Admin UI and templates have been removed; URLs redirect to /dashboard/. Former items were:

| Key | Label | URL name | Path prefix |
|-----|--------|----------|-------------|
| overview | Overview | super_admin:overview | /dashboard/super-admin/ |
| partners | Partners | super_admin:partners | ... |
| api_access | API & Access | super_admin:api_access | ... |
| finance | Finance | super_admin:finance | ... |
| security | Security | super_admin:security | ... |
| system | System | super_admin:system | ... |
| system_control | System Control | super_admin:system_control | ... |
| health_center | Health Center | super_admin:health_center | ... |
| job_history | Job History | super_admin:job_history | ... |
| compliance | Compliance | super_admin:compliance | ... |
| growth | Growth | super_admin:growth | ... |
| emergency | Emergency | super_admin:emergency | ... |
| alerts | Alerts | super_admin:alerts | ... |
| reports | Reports | super_admin:reports | ... |

Footer: “← Governance” → governance:dashboard; “Back to Admin” → dashboard_admin. All resolve.

---

## 2. Angular nav tree

### 2.1 ParkPe (frontend-space/projects/parkpe)

**Layout:** app-layout.component; nav from `navItems` array and fixed icon links.

| Label | path | Route (from app/feature routes) |
|-------|------|---------------------------------|
| Parking | /parking | (comingSoon) |
| Bills (BBPS) | /bbps | bbps |
| Vouchers | /vouchers | vouchers |
| FASTag | /fastag | (comingSoon) |
| Challan | /challan | challan |
| Payments | /payment/history | payment/history |
| Reports | /payment/reports | payment/reports |
| Connect | /connect | connect |

Icon links: /dashboard, /profile/view, /settings. Drawer repeats same nav + /settings. In-page links observed: /connect/vehicles, /connect/vehicles/add, /connect/scan, /connect/chats, /connect/info, /vouchers, /challan, /fastag, /auth/login, /auth/register, /auth/forgot-password, /home, /. All align with typical ParkPe app routes (app.routes.ts and feature routes).

### 2.2 Payswap (frontend-space/projects/payswap)

No sidebar/nav links found in grep (no routerLink/path in payswap app templates in the result set). Payswap app may be minimal or use different structure; not fully audited here.

### 2.3 Payswap-Governance (frontend-space/projects/payswap-governance)

**Layout:** governance-layout.component.html.

| Label | routerLink | Route |
|-------|------------|--------|
| Overview | /dashboard | dashboard |
| APIs | /apis | apis |
| Partners | /partners | partners |
| Emergency | /emergency | emergency |
| Audit | /audit | audit |
| Settings | /settings | settings |

app.routes.ts: dashboard, apis, partners, emergency, audit, settings — all match. Logout link present.

---

## 3. Findings: dead, duplicate, unused, inconsistent

### Dead links

- **None confirmed.** All Django `{% url %}` names and Angular routes checked exist. No link was found pointing to a removed or renamed route.

### Duplicate links

- **Same destination, different labels/places:**  
  - “Partners” in Governance (governance:partners) vs “Partner Management” in main sidebar (admin_reseller_partner_dashboard). Different pages: Governance partners = API subscriptions; Partner Management = /admin/partners/ (reseller CRUD). So not same destination; labels can be confused (“Partners” vs “Partner Management”).  
  - “Back to Admin” vs “← Admin” in governance pages — same target (dashboard_admin).  
  - Super Admin “Emergency” vs Governance “Emergency” — different views (super_admin:emergency vs governance:emergency); both can toggle kill switch (same cache key). Two entry points, not duplicate links to same URL.

### Unused tabs / routes

- **Governance:** “Control Tower” and “System status” are both in the governance nav; they are also exposed at top-level dashboard paths. If the governance include defines control_tower and system_status with same view names, those tabs are used. No evidence of a route that exists but is never linked.  
- **ParkPe:** “Parking”, “FASTag”, “Challan” marked comingSoon in nav — routes may exist but be gated or placeholder; still linked in sidebar.

### Inconsistent naming

- **“Control Tower” vs “Governance”:** Main sidebar label is “Control Tower” and goes to governance:dashboard (Overview). Governance inner nav has both “Overview” and “Control Tower” (control_tower). So “Control Tower” in sidebar = Governance dashboard; “Control Tower” in governance = Control Tower page. Same term, two different pages.  
- **“Partners” vs “Partner Management”:** Governance “Partners” = API subscriptions; sidebar “Partner Management” = Reseller partners. Intentional but naming could be clearer (e.g. “Partner API access” vs “Partner management”).  
- **“Back to Admin” vs “← Admin”:** Inconsistent label for same target (dashboard_admin) across governance templates.

---

*End of Step 7 — Navigation Audit.*
