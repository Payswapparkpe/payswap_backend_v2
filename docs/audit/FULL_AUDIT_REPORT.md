# Phase 0: Full System Audit — Master Report

**Read-only audit. No code changes. No solutions or refactor suggestions — only findings.**

This document summarizes the ten audit steps and consolidates findings. Each step has a dedicated report under `docs/audit/`.

---

## Step summaries

### Step 1 — Repo structure map  
**Output:** [structure_map.md](structure_map.md)

The repo has Django apps `api`, `portal`, `api_management`, and project `core`. The frontend-space is an Angular workspace with projects `payswap`, `parkpe`, `payswap-governance`, and library `shared`. Entry points: Django `core/urls.py` and `manage.py`; Angular `main.ts` and `app.routes.ts` per app. Portal templates are under `portal/templates/portal/` with 150+ HTML files grouped by feature (super_admin, governance, admin, vouchers, parkpe, etc.). API URL tree is versioned (v1, v2, enterprise, control, dashboard, auth, connect, bbps, payment, voucher) and internal health/run-job live under `internal/`.

### Step 2 — URL & view inventory  
**Output:** [url_view_inventory.md](url_view_inventory.md)

All Django and Angular routes were extracted and grouped by purpose (Auth, Dashboard, Partner, Billing, Governance, Super Admin, Operations, API ParkPe, Analytics). Findings: duplicate mounts (e.g. Super Admin at `/dashboard/super-admin/` and `/super-admin/`; `/partners/` and `/reseller/` same view); deprecated but active `/api/v1/control/*` in favour of `/api/control/`; kill switch and control tower exposed in both Governance and Super Admin; multiple health endpoints (internal, v1, v2).

### Step 3 — UI screen catalog  
**Output:** [ui_catalog.md](ui_catalog.md)

Portal (Django) and Angular (ParkPe, payswap-governance) screens were catalogued with route, view/component, and data source. Overlaps: multiple partner UIs (reseller, partners, partner console, admin partners, super admin partners, governance partners); multiple “dashboard” or “overview” screens; billing/finance spread across admin partner pricing/settlement, Super Admin Finance, and Enterprise API; kill switch/emergency in both Governance and Super Admin; several “settings” entry points.

### Step 4 — Command inventory  
**Output:** [command_inventory.md](command_inventory.md)

Management commands in `portal` and `api_management` and scripts in `scripts/` were listed with purpose and related service/model. Nine commands have a UI trigger (Super Admin System Control or /internal/run-job/): audit_partners, reconcile_daily, run_billing_cycle, generate_invoices, fraud_scan, archive_apilog, compute_sla, compliance_pack, enterprise_export. All others are CLI-only (or cron). Overlap: send_parkpe_test_email exists as both command and script. Many test_* and seed_* commands; reset_db, clean_and_seed, seed_data are destructive/dev-only.

### Step 5 — Service & business logic map  
**Output:** [service_map.md](service_map.md)

Services in `portal/services/`, `api_management/services/`, and vendor clients were mapped. Core flows (billing, auth, governance, settlement, SLA, fraud, Super Admin job run) were traced from entry to exit. Duplicated logic: two entry points for “run command” (Super Admin System run_command vs System Control run_job — one creates SystemJobRun, one does not); kill switch toggled from two UIs (same cache key); multiple paths to send email (email_queue_service, notification_service_v2, direct send, resend_pending_emails).

### Step 6 — Data model map  
**Output:** [data_model_map.md](data_model_map.md)

Portal models live in `portal/models/_monolith.py` (single file; table prefix `portal_*`). API Management models in `api_management/models.py` (prefix `api_management_*`). Models were grouped by domain (Auth/User, Partner/Billing, Wallet, Vouchers, Connect, ParkPe, BBPS, Services/Vendor, Tickets, Logging). Findings: two API log concepts (CashfreeAPILog vs APILog); multiple audit/log tables (LogEntry, GiftVoucherAuditLog, ControlAuditLog); partner “subscription” in two places (PartnerVendorAssignment vs PartnerAPISubscription); APIKeyUsageLog vs APILog overlap; no separate wallet app.

### Step 7 — Navigation audit  
**Output:** [navigation_audit.md](navigation_audit.md)

Django sidebar (partials/sidebar_menu.html), governance inner nav, Super Admin sidebar, and Angular ParkPe/payswap-governance nav were audited. No confirmed dead links. Duplicate or confusing: “Partners” (governance) vs “Partner Management” (sidebar) — different pages; “Control Tower” in sidebar points to governance dashboard, “Control Tower” in governance points to control tower page (same term, two targets); “Back to Admin” vs “← Admin” inconsistent label for same target.

### Step 8 — Test coverage map  
**Output:** [test_coverage.md](test_coverage.md)

Test files in `api/tests/` and `portal/tests/` were listed with targets. Coverage exists for auth, governance API, partner (subscription + accounting), Super Admin system control, voucher, wallet, execution engine, logging, analytics, health/smoke. Gaps: no tests for billing/run_billing_cycle/invoices, Connect, BBPS (only e2e command), api_management services (command_runner, job_run, system_job, control_audit, control_tower_health), most portal views, Celery tasks. Duplicate tests: superuser/profile in test_user_manager and test_authentication; profile completion in test_profile_completion and test_authentication; lockout behavior in test_otp_lockout and test_authentication.

### Step 9 — Config & feature flags audit  
**Output:** [config_audit.md](config_audit.md)

Settings, .env.example, PayswapConfig, and FeatureFlag usage were scanned. Only one feature flag code is used in code: "api_access" (middleware). Other flags in DB have no effect unless code checks them. Two “kill API” mechanisms: Redis key (UI-toggled) and env API_GOVERNANCE_KILL_SWITCH. API_LOG_SAMPLE_RATE and API_GOVERNANCE_* are not in .env.example.

### Step 10 — End-to-end flow trace  
**Output:** [flow_trace.md](flow_trace.md)

Major flows (ParkPe Connect, BBPS, Billing, Partner onboarding, Governance, Super Admin job run, ParkPe Auth/Payment/Voucher, Enterprise) were traced from entry (UI or cron) through services/APIs and vendors/DB to exit. Key files and one-sentence narratives were documented per flow.

### Phase 11 — End-to-end testing  
**Output:** [e2e_test_report.md](e2e_test_report.md)

Pytest was run on `portal/tests` and `api/tests` (132 tests total). API suite: 40 passed, 2 skipped, 0 failed. Portal suite: multiple failures observed (e.g. profile completion template missing, superuser profile, OTP dual delivery, partner accounting, voucher issuance); full portal run was slow/incomplete. No billing or SLA-specific test suites exist. No fixes applied; results documented for later remediation.

---

## Findings

### Duplications

- **URLs / views:** `/partners/` and `/reseller/` use the same ResellerDashboardView. Super Admin is mounted at `/dashboard/super-admin/` and `/super-admin/` (same app, two prefixes). Governance and Super Admin both expose kill switch and emergency UIs (same Redis key).
- **Run command:** Two entry points — Super Admin “System” run_command (no SystemJobRun) and “System Control” run_job (creates SystemJobRun); same ALLOWED_COMMANDS.
- **Control / governance:** `/api/v1/control/*` still present although deprecated in favour of `/api/control/`. Control Tower and System Status appear in both top-level dashboard paths and governance include.
- **Partner UIs:** Reseller dashboard, partners alias, partner console, admin partners, super admin partners, governance partners — multiple UIs for “partner” concepts.
- **Dashboards / overview:** Role dashboards (admin, employee, super, etc.), Governance dashboard, Control Tower, System status, Super Admin overview, ParkPe dashboard, payswap-governance dashboard.
- **Send email:** email_queue_service, notification_service_v2, direct send_mail, resend_pending_emails command.
- **Tests:** Superuser/profile and profile completion tested in more than one file; lockout-style behavior in OTP and login tests.

### Dead zones

- **Dead links:** None confirmed; all audited URL names and Angular routes exist.
- **Unused feature flags:** Only "api_access" is checked in code; other flag codes in DB have no behavioral effect unless code is added.
- **Deprecated but active:** `/api/v1/control/*` is still in use although deprecated in favour of `/api/control/`.

### Ownership gaps

- **Billing:** Logic in billing_service and run_billing_cycle/generate_invoices; no single “billing app”; spread across admin partner pricing/settlement, Super Admin Finance, and Enterprise API.
- **Kill switch:** Two UIs (Governance Emergency, Super Admin Emergency) and two mechanisms (Redis key, env var); audit trail and documentation of “who wins” not fully clarified in audit.
- **Partner “subscription” vs “vendor assignment”:** PartnerVendorAssignment (portal) vs PartnerAPISubscription (api_management); different layers (vendor assignment vs API allowlist) but both define “what can this partner use.”

### Risk areas

- **Billing:** No automated tests for billing_service, run_billing_cycle, generate_invoices, or settlement flow; critical for revenue.
- **Connect / BBPS:** No unit tests for connect views or bbps_service; only e2e command for Mobikwik BBPS.
- **api_management services:** command_runner_service, job_run_service, system_job_service, control_audit_service, control_tower_health not covered by dedicated tests (job run tested from portal side only).
- **Run command split:** One path records SystemJobRun and audit; the other does not — inconsistent observability for the same allowed commands.
- **Env vs .env.example:** API_LOG_SAMPLE_RATE and API_GOVERNANCE_* not documented in .env.example; production may miss them.

### UI gaps

- **Commands without UI:** All management commands except the nine runnable from System Control (or /internal/run-job/) have no UI button — e.g. setup_super_admin, backup_verify, load_bbps_operators, seed_*, test_*, fix_stuck_batches, system_watchdog, sync_api_registry. Some are one-off/setup; others (e.g. system_watchdog) might benefit from visibility.
- **Single billing/settlement UI:** No unified “billing” app; partner settlement and invoice download are under admin partner and partner console; Super Admin Finance is separate.

### Command overload

- **Many test_* and seed_* commands:** test_all_api_responses, test_mobikwik_bbps, test_euronet_bbps, test_paypoint_aeps, test_voucher_logging, test_all_cashfree_apis, test_notifications, test_all; seed_data, seed_services, seed_vendor_apis, seed_payment_services, seed_api_products, seed_connect_predefined_messages, etc. Overlap with UI only for the nine “run job” commands; rest are CLI/cron/dev.
- **Duplicate capability:** send_parkpe_test_email as management command and as script in scripts/.

### Tech debt hotspots

- **Portal models:** Single _monolith.py with all portal models; no per-domain split; high coupling and file size.
- **Two API log tables:** CashfreeAPILog (vendor-specific) vs APILog (registry-linked, SLA); overlapping “log API calls” concern.
- **Multiple audit tables:** LogEntry, GiftVoucherAuditLog, ControlAuditLog — same “audit trail” idea in different domains.
- **Naming inconsistency:** “Control Tower” used for both governance dashboard and control tower page; “Partners” vs “Partner Management” for different pages.
- **Super Admin namespace:** Mounted under two URL prefixes; Django namespace warning possible (super_admin not unique across mounts).

---

## Deliverables checklist

| # | Output | Path |
|---|--------|------|
| 1 | Structure map | docs/audit/structure_map.md |
| 2 | URL & view inventory | docs/audit/url_view_inventory.md |
| 3 | UI screen catalog | docs/audit/ui_catalog.md |
| 4 | Command inventory | docs/audit/command_inventory.md |
| 5 | Service map | docs/audit/service_map.md |
| 6 | Data model map | docs/audit/data_model_map.md |
| 7 | Navigation audit | docs/audit/navigation_audit.md |
| 8 | Test coverage map | docs/audit/test_coverage.md |
| 9 | Config audit | docs/audit/config_audit.md |
| 10 | Flow trace | docs/audit/flow_trace.md |
| 11 | E2E test report | docs/audit/e2e_test_report.md |
| 12 | Full audit report | docs/audit/FULL_AUDIT_REPORT.md |

---

## Final result — answers (audit only; no solutions)

After this audit we can answer:

| Question | Answer (from audit) |
|----------|---------------------|
| **What is duplicate?** | URLs (partners/reseller, super_admin two prefixes); run-command (System vs System Control); partner UIs; dashboards; email send paths; some tests. |
| **What is useless?** | Unused feature flag codes (only "api_access" used); deprecated api/v1/control/* still active; some test_* / seed_* commands are dev-only. |
| **What is missing in UI?** | Most management commands (only 9 in System Control); unified billing/settlement view; API_GOVERNANCE_* / API_LOG_SAMPLE_RATE config. |
| **What should be removed later?** | Not prescribed (audit is facts only). Candidates: duplicate URL mounts, one of the run-command entry points, deprecated v1 control routes. |
| **What needs admin dashboard?** | Commands without UI (e.g. system_watchdog, load_bbps_operators, resend_pending_emails); single place for billing/settlement visibility. |
| **What is risky?** | Billing/Connect/BBPS untested; run-command split (one path no SystemJobRun); two kill mechanisms; env vars not in .env.example. |
| **What is solid?** | API tests (governance, partner, smoke, v2) pass; Super Admin system control tests pass; auth, wallet, execution engine, logging tests mostly pass; production smoke and partner governance tests green. |

---

**End of Full System Audit. No fixes or refactors — only facts and findings. Wait for approval before cleanup.**
