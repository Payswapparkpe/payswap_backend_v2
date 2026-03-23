# Consolidation Phase — Summary

This document summarizes the three consolidation deliverables and recommends a cleanup order. It does not add new analysis—only synthesis. It aligns with the Phase 0 audit’s **12 deliverables** (including [e2e_test_report.md](../audit/e2e_test_report.md) and [FULL_AUDIT_REPORT.md](../audit/FULL_AUDIT_REPORT.md)) and the audit’s **Final result — answers** table (what is duplicate, useless, missing in UI, risky, solid).

**Consolidation deliverables:**

- [cleanup_plan.md](cleanup_plan.md) — Phase A: duplication groups, canonical vs deprecated, migration paths, effort.
- [command_to_ui_mapping.md](command_to_ui_mapping.md) — Phase B: command classification, System Control UI spec, CLI-only rationale.
- [unified_control_center.md](unified_control_center.md) — Phase C: single admin hierarchy, screens/routes/views/services/permissions, sidebar, naming.

---

## 1. Major duplications

- **URL/route:** `/partners/` alias of `/reseller/` (canonical: `/reseller/`; redirect partners → reseller). Super Admin mounted at two prefixes (canonical: `/dashboard/super-admin/`; remove `/super-admin/`). Run command has two entry points (canonical: System Control run_job with SystemJobRun; deprecate System run_command). `/api/v1/control/*` deprecated in favour of `/api/control/`. Kill switch: one canonical UI (e.g. Governance Emergency); other redirect or same backend.
- **UI:** Partner UIs are different views of partner (admin CRUD, reseller self-service, partner console, Super Admin read-only, Governance subscriptions); consolidate under unified Control Center naming. Kill switch: single screen. Settings: keep separate; unify labels only.
- **Command:** send_parkpe_test_email — canonical: management command; script in `scripts/` legacy.
- **Service/logic:** Run command: canonical path via job_run_service; deprecate direct command_runner from System run_command. Send email: multiple paths documented; recommend queue; no removal in consolidation.
- **Navigation:** "Control Tower" used for two targets → rename sidebar to "Governance" and keep "Control Tower" for health page. "Partners" vs "Partner Management" → "Partner API access" (governance) and "Partners" (admin). "Back to Admin" vs "← Admin" → standardize to "Back to Admin."

---

## 2. CLI dependencies

- **By class:** Operational (recurring): 9 already in System Control + 6–8 proposed (system_watchdog, resend_pending_emails, fix_stuck_batches, process_batch_sync, simulate_vendor_down, backup_verify, sync_api_registry, load_bbps_operators optional). Maintenance: sync_api_registry, load_bbps_operators. One-time setup: all seed_*, setup_*, ensure_*, migrate_*, assign_default_vendors, etc. Deprecated/dev: test_*, reset_db, clean_and_seed, seed_data, fix_ticket_migration, etc.
- **UI today:** 9 commands have UI (audit_partners, reconcile_daily, run_billing_cycle, generate_invoices, fraud_scan, archive_apilog, compute_sla, compliance_pack, enterprise_export). Rest CLI-only.
- **Proposed:** Add to System Control: system_watchdog, resend_pending_emails, fix_stuck_batches, process_batch_sync, simulate_vendor_down, backup_verify, sync_api_registry (and optionally load_bbps_operators). All operational commands that should be runnable by ops without SSH should appear in System Control with run button, status, last run, logs, error, permission (see command_to_ui_mapping.md).

---

## 3. UI gaps

- **Commands without UI:** Most management commands (one-time setup, test_*, destructive) correctly stay CLI-only. Operational gaps: system_watchdog, resend_pending_emails, fix_stuck_batches, process_batch_sync, simulate_vendor_down, backup_verify, sync_api_registry — addressed by Phase B mapping (add to System Control).
- **Billing/settlement spread:** Billing run (System Control) + admin partner pricing/settlement + Super Admin Finance + Enterprise API. Addressed by Phase C: Operations → Billing/Settlement/Reconciliation with clear links from one Control Center.
- **Partner/settings/kill-switch entry points:** Multiple entry points documented in cleanup_plan and unified_control_center; single sidebar and naming (Phase C) reduce confusion. Kill switch: one canonical screen.

---

## 4. Ownership gaps

- **Billing:** No single "billing app"; Phase C assigns Operations → Billing (run_billing_cycle, generate_invoices, admin partner pricing) and Settlement (admin settlement, enterprise API) so ownership is "Operations" section.
- **Kill switch:** Two UIs, one backend; Phase C assigns to Super Admin → Kill Switch (or Governance → Emergency) as single logical owner; other UI redirects.
- **Partner subscription vs vendor assignment:** PartnerVendorAssignment (portal) vs PartnerAPISubscription (api_management) remain separate models; Phase C assigns "Partner API access" (Governance) for subscriptions and "Partners" / "Vendor Control" (Partner Management / Governance) for vendor assignment so both are visible under Control Center with clear names.

---

## 5. Risk areas (to address in later phases)

- **Run command split:** One path (System run_command) does not create SystemJobRun; observability gap. Addressed in cleanup_plan: deprecate run_command and route all runs through run_job.
- **Billing untested:** No automated tests for billing_service, run_billing_cycle, generate_invoices (per audit). Consolidation does not add tests; recommend separate test phase.
- **Env vs .env.example:** API_LOG_SAMPLE_RATE and API_GOVERNANCE_* not in .env.example. Document in config/ops runbook; consolidation does not change code.
- **Destructive commands (High risk per audit):** reset_db, clean_and_seed, seed_data must never be triggerable from production UI; remain CLI-only (see command_to_ui_mapping.md).
- **Portal/E2E test gaps (per [e2e_test_report.md](../audit/e2e_test_report.md)):** API suite: 40 passed, 2 skipped, 0 failed. Portal suite (partial run): ~74 passed, ~12+ failed, ~4 errors. Observed failures: profile completion (e.g. TemplateDoesNotExist portal/profile/complete.html), superuser profile creation, OTP rate limiting, OTP dual delivery (2 tests), partner accounting (2 tests), profile completion save, user manager superuser profile, voucher service issuance. No billing or run_billing_cycle tests; no SLA unit tests in the 132 collected. Remediation is outside consolidation scope.

---

## 6. Recommended cleanup order

1. **URL/nav renames and redirects (low risk, S)**  
   Redirect `/partners/` → `/reseller/`. Rename sidebar "Control Tower" → "Governance" (overview). Rename "Partners" (governance) → "Partner API access", and clarify "Partners" (admin). Standardize "Back to Admin" / "← Admin" → "Back to Admin."

2. **Consolidate Super Admin to one mount and run_command → run_job (M)**  
   Remove `/super-admin/` mount; keep `/dashboard/super-admin/`; update all links. Deprecate System run_command view or make it call job_run_service so every run creates SystemJobRun.

3. **Deprecate api/v1/control with docs/headers (M)**  
   Add deprecation headers on `/api/v1/control/*`; document migration to `/api/control/`; optionally redirect or maintain v1 for a sunset period.

4. **Implement Phase C sidebar and section grouping (M)**  
   Introduce single Control Center sidebar (Super Admin, Governance, Operations, Partner Management, Analytics) with expandable sections and the naming from unified_control_center.md. Keep existing routes; change only nav and labels.

5. **Add new System Control commands from Phase B (S–M)**  
   Add system_watchdog, resend_pending_emails, fix_stuck_batches, process_batch_sync, simulate_vendor_down, backup_verify, sync_api_registry to ALLOWED_COMMANDS and System Control UI (run button, dry-run where supported, status, last run, logs, error).

6. **Model/audit consolidation deferred (L)**  
   API log separation (APILog vs CashfreeAPILog), audit tables (LogEntry, GiftVoucherAuditLog, ControlAuditLog), and APIKeyUsageLog vs APILog overlap remain as-is; document only. No schema or model merge in consolidation.

---

## Audit reference

The consolidation plan is driven by the Phase 0 audit’s **12 deliverables** (structure, URL/view, UI catalog, command inventory, service map, data model map, navigation, test coverage, config, flow trace, **e2e test report**, full audit report). The [e2e_test_report.md](../audit/e2e_test_report.md) documents test run results (API 40 passed / 2 skipped; Portal ~74 passed, ~12+ failed, ~4 errors; no billing/SLA tests). For the fact base (what is duplicate, useless, missing in UI, risky, solid), see [FULL_AUDIT_REPORT.md](../audit/FULL_AUDIT_REPORT.md) — "Final result — answers" table. Wait for approval before executing cleanup.

*End of Consolidation Summary.*
