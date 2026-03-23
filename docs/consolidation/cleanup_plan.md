# Consolidation Phase A — Duplication Cleanup Plan

**Analysis only. No code edits. No deletions without replacement.**

This document groups duplications from the Phase 0 audit into six categories. For each duplicate group: canonical (keep), deprecated/alias, dependencies, risk, safe migration path, and effort (S/M/L). No removal actions are prescribed—only analysis to support later cleanup.

**Inputs (audit deliverables — 12 total):** [FULL_AUDIT_REPORT.md](../audit/FULL_AUDIT_REPORT.md), [structure_map.md](../audit/structure_map.md), [url_view_inventory.md](../audit/url_view_inventory.md), [ui_catalog.md](../audit/ui_catalog.md), [command_inventory.md](../audit/command_inventory.md), [service_map.md](../audit/service_map.md), [data_model_map.md](../audit/data_model_map.md), [navigation_audit.md](../audit/navigation_audit.md), [test_coverage.md](../audit/test_coverage.md), [config_audit.md](../audit/config_audit.md), [flow_trace.md](../audit/flow_trace.md), [e2e_test_report.md](../audit/e2e_test_report.md). This cleanup plan aligns with the audit’s findings (duplications, risk areas, ownership gaps) and does not contradict Step 11 (E2E test report) or the audit’s "Final result — answers" table.

---

## 1. URL / route duplicates

| Group | Canonical (keep) | Deprecated / alias | Dependencies | Risk | Safe migration path | Effort |
|-------|------------------|--------------------|--------------|------|---------------------|--------|
| Reseller vs Partners | `/reseller/` (primary) | `/partners/` (alias, same ResellerDashboardView) | Sidebar, bookmarks, docs, `partner_dashboard` URL name | Low | Redirect `/partners/` → `/reseller/`; keep one route; update any links using `partner_dashboard` to `reseller_dashboard` | S |
| Super Admin mount | `/dashboard/super-admin/` (under dashboard) | `/super-admin/` (second mount) | Nav "Super Admin" links, governance footer "Super Admin", super_admin namespace | Medium (Django namespace warning) | Remove one mount (e.g. drop `/super-admin/`); standardize all links to `/dashboard/super-admin/` | M |
| Run command | System Control run_job (SuperAdminRunJobView → job_run_service, SystemJobRun + audit) | System run_command (SuperAdminRunCommandView → command_runner_service, no SystemJobRun) | System Control UI, POST `/internal/run-job/`, ALLOWED_COMMANDS | Low | Deprecate run_command view; route all runs through run_job so every run is logged | S |
| Control API | `/api/control/*` | `/api/v1/control/*` | Payswap-governance Angular app or other API clients may call v1 | Medium | Add deprecation headers on v1; document migration to `/api/control/`; optional redirect or proxy | M |
| Health endpoints | Keep all with clear roles | — | `/internal/health/` (ops), `/api/v1/health/`, `/api/v2/health/` (different consumers) | — | Document purpose of each; no removal | — |
| Kill switch UI | One canonical (e.g. Governance Emergency) | Super Admin Emergency (duplicate UI, same Redis key) | Governance nav, Super Admin nav, both write GOV_KILL_SWITCH_CACHE_KEY | Low | Keep single UI (e.g. Governance Emergency); make Super Admin Emergency redirect to it, or keep both with same backend | S |

---

## 2. UI screen duplicates

| Group | Canonical / primary | Other (distinct purpose or duplicate) | Dependencies | Risk | Safe migration path | Effort |
|-------|---------------------|--------------------------------------|--------------|------|---------------------|--------|
| Partner UIs | Admin `/admin/partners/` (full CRUD) | `/reseller/` (self-service), `/partner/dashboard/` (console), Super Admin partners (read-only/ops), Governance partners (API subscriptions). Each has distinct purpose. | Sidebar "Partner Management", governance "Partners", Super Admin "Partners" | Low | Treat as "different views of partner" not true duplicates; unify under single Control Center section with clear naming (Phase C) | M |
| Dashboards / overview | One "Overview" per section in unified Control Center | Role dashboards (admin, employee, super, etc.), Governance dashboard, Control Tower page, System status, Super Admin overview | Role-based redirects, nav links | Low | Unified control center single Overview per section; deprecate redundant role dashboards only if replaced by redirect | M |
| Kill switch / emergency | One screen (e.g. Governance → Emergency) | Super Admin → Emergency (same backend) | Both UIs toggle same Redis key | Low | One canonical screen; other becomes redirect or remove from nav | S |
| Settings | Keep separate by scope | User settings (`/settings/`), Governance settings, Super Admin "API & Access" / "Security" | Different audiences | — | Unify only naming: "User settings", "Governance settings", "System settings" | S |

---

## 3. Management command duplicates

| Group | Canonical (keep) | Deprecated | Dependencies | Risk | Safe migration path | Effort |
|-------|------------------|------------|--------------|------|---------------------|--------|
| send_parkpe_test_email | Management command `send_parkpe_test_email` (runnable from run-job) | Script `scripts/send_parkpe_test_email.py` | Dev/ops manual runs | Low | Document script as legacy; prefer command for consistency and audit trail | S |

---

## 4. Service / logic duplicates

| Group | Canonical (keep) | Deprecated / alternate path | Dependencies | Risk | Safe migration path | Effort |
|-------|------------------|-----------------------------|--------------|------|---------------------|--------|
| Run command | job_run_service (creates SystemJobRun, control_audit_service) | Direct command_runner_service from System run_command (no SystemJobRun) | SuperAdminRunCommandView, SuperAdminRunJobView | Low | Remove or refactor System run_command to call job_run_service so all runs are logged | S |
| Kill switch | Single backend (Redis GOV_KILL_SWITCH_CACHE_KEY) | Duplicate UIs only (Governance + Super Admin) | Both UIs | — | Consolidate to one UI (Phase C); backend unchanged | S |
| Send email | email_queue_service (queue) recommended for consistency | notification_service_v2, direct send_mail, resend_pending_emails command | Multiple call sites | — | Document as "multiple paths"; recommend queue for new code. Not removable without refactor. Defer. | L (out of scope) |

---

## 5. Model / table duplicates

| Group | Canonical / role | Other | Dependencies | Risk | Safe migration path | Effort |
|-------|-------------------|-------|--------------|------|---------------------|--------|
| API logs | APILog (api_management) — SLA, governance, registry-linked | CashfreeAPILog (portal) — vendor-specific | APILog: middleware, compute_sla; CashfreeAPILog: Cashfree flows | — | Keep both; document separation (governance vs vendor debug). No removal. | — |
| Audit tables | Each domain keeps its own | LogEntry (generic), GiftVoucherAuditLog (voucher), ControlAuditLog (control actions) | Different domains | — | Document; no consolidation without schema change. Defer. | — |
| Partner subscription vs vendor assignment | Both kept; different concerns | PartnerVendorAssignment (portal) = vendor assignment; PartnerAPISubscription (api_management) = API allowlist | Partner CRUD, governance API | — | Unify only in UI: one "Partner capabilities" section showing both. No model merge. | M (UI only) |
| APIKeyUsageLog vs APILog | APILog broader (user + api_key + anon), registry-linked | APIKeyUsageLog (portal) — may be legacy/partner-facing | Usage reporting | — | Document overlap; consider deprecating APIKeyUsageLog only after verifying no unique use. Defer. | L |

---

## 6. Navigation duplicates

| Group | Canonical / desired | Current issue | Dependencies | Risk | Safe migration path | Effort |
|-------|----------------------|---------------|--------------|------|---------------------|--------|
| "Control Tower" label | Sidebar: "Governance" or "Governance Overview"; inner: "Control Tower" (health page) | Sidebar "Control Tower" → governance dashboard (Overview); inner "Control Tower" → control tower page. Same term, two targets. | sidebar_menu.html, governance templates | Low | Rename sidebar link to "Governance" or "Governance Overview"; keep inner "Control Tower" for health/control page | S |
| "Partners" vs "Partner Management" | "Partner API access" (governance); "Partners" or "Partner management" (admin) | Governance "Partners" = API subscriptions; sidebar "Partner Management" = admin CRUD. Labels confusing. | Governance nav, sidebar | Low | Rename to "Partner API access" (governance) and "Partners" or "Partner management" (admin) | S |
| "Back to Admin" vs "← Admin" | Single label e.g. "Back to Admin" | Inconsistent label for same target (dashboard_admin) across governance templates | Governance templates | Low | Standardize to "Back to Admin" everywhere | S |

---

## Reminder

- **No deletions without replacement:** Every deprecated URL, screen, or entry point must have a redirect or clear replacement before removal.
- **No feature removal:** Consolidation is about reducing duplication and clarifying ownership, not removing capability.
- **Effort:** S = small (hours), M = medium (days), L = large (deferred or multi-sprint).

*End of Phase A — Cleanup Plan.*
