# Consolidation Phase B — Command to Admin UI Mapping

**Design only. No implementation.**

This document classifies every management command from the audit, maps operational commands to a Super Admin → System Control UI design, and states why some commands remain CLI-only.

**Input:** [command_inventory.md](../audit/command_inventory.md) (including §4 Commands: UI Exists? and Risk summary). Risk levels below align with that audit section where applicable.

---

## 1. Command classification and UI mapping

Risk (per audit §4): **Low** (audited/run once/dev only), **Medium** (manual/cron/ops), **High** (destructive). Commands with UI today are Low risk (audited); destructive commands are High and must remain CLI-only.

### Portal management commands

| Command | Class | UI today | Proposed UI | Risk (audit) | Reason if CLI-only |
|---------|-------|----------|-------------|--------------------|
| audit_partners | Operational | Yes | Same | Low | — |
| reconcile_daily | Operational | Yes | Same | Low | — |
| run_billing_cycle | Operational | Yes | Same | Low | — |
| generate_invoices | Operational | Yes | Same | Low | — |
| fraud_scan | Operational | Yes | Same | Low | — |
| compliance_pack | Operational | Yes | Same | Low | — |
| enterprise_export | Operational | Yes | Same | Low | — |
| resend_pending_emails | Operational | No | Add to System Control | Medium | Recurring ops; retry failed emails |
| fix_stuck_batches | Operational | No | Add to System Control | Medium | Recurring ops; fix voucher batches |
| process_batch_sync | Operational | No | Add to System Control | Medium | Recurring ops; process batch sync |
| simulate_vendor_down | Operational | No | Add to System Control (dry-run) | Medium | Ops verification; supports dry-run |
| backup_verify | Operational | No | Add to System Control (dry-run) | Medium | Pre-deploy / ops; supports dry-run |
| sync_api_registry | Maintenance | No | Add to System Control | Medium | Periodic sync after URL config changes |
| load_bbps_operators | Maintenance | No | Add to System Control (optional) | Medium | Run after operator list updates |
| setup_super_admin | One-time setup | No | None | Low | Run once per env; no recurring need |
| setup_roles | One-time setup | No | None | Low | Run once per env |
| create_internal_api_keys | One-time setup | No | None | Medium | Run once or per new internal consumer |
| ensure_parkpe_partner | One-time setup | No | None | Medium | Bootstrap ParkPe partner |
| migrate_parkpe_partner | One-time setup | No | None | Medium | Migration / bootstrap |
| ensure_parkpe_voucher_brand | One-time setup | No | None | Medium | Bootstrap voucher brand |
| set_parkpe_default_pg | One-time setup | No | None | Medium | Bootstrap payment config |
| assign_default_vendors | One-time setup | No | None | Medium | Bootstrap vendor assignment |
| mobikwik_bbps_clear_token_cache | One-time / ops | No | None | Low | Rare cache clear; safety to keep CLI |
| seed_connect_predefined_messages | One-time setup | No | None | Medium | Environment bootstrap |
| seed_vendor_apis | One-time setup | No | None | Medium | Environment bootstrap |
| seed_services | One-time setup | No | None | Medium | Environment bootstrap |
| seed_payment_services | One-time setup | No | None | Medium | Environment bootstrap |
| seed_data | Deprecated / dev | No | None | **High** | Destructive; must not be in production UI |
| clean_and_seed | Deprecated / dev | No | None | **High** | Destructive; dev only |
| reset_db | Deprecated / dev | No | None | **High** | Destructive; must not be triggerable from UI |
| send_parkpe_test_email | Operational (diagnostic) | No | Same or None | Low | Could add to UI for support; low priority |
| test_all_api_responses | Deprecated / dev | No | None | Low | Dev/QA only; not production ops |
| verify_api_key_autofill | Deprecated / one-off | No | None | Low | Diagnostic; one-off |
| test_api_and_check_logs | Deprecated / dev | No | None | Low | Dev/QA only |
| test_euronet_bbps | Deprecated / dev | No | None | Low | Dev/QA only |
| test_paypoint_aeps | Deprecated / dev | No | None | Low | Dev/QA only |
| test_all_bbps_operators | Deprecated / dev | No | None | Low | Dev/QA only |
| test_mobikwik_bbps | Deprecated / dev | No | None | Low | Dev/QA only |
| test_voucher_logging | Deprecated / dev | No | None | Low | Dev/QA only |
| test_all_cashfree_apis | Deprecated / dev | No | None | Low | Dev/QA only |
| test_notifications | Deprecated / dev | No | None | Low | Dev/QA only |
| test_all | Deprecated / dev | No | None | Low | Dev/QA only |
| check_ticket_tables | Deprecated / one-off | No | None | Low | One-off diagnostic |
| fix_ticket_migration | Deprecated / one-off | No | None | Low | One-off migration fix |
| compare_mobikwik_operators | Deprecated / dev | No | None | Low | Diagnostic / dev |

### api_management management commands

| Command | Class | UI today | Proposed UI | Risk (audit) | Reason if CLI-only |
|---------|-------|----------|-------------|--------------|--------------------|
| compute_sla | Operational | Yes | Same | Low | — |
| archive_apilog | Operational | Yes | Same | Low | — |
| system_watchdog | Operational | No | Add to System Control | Medium | Recurring; evaluates SLA status |
| sync_api_registry | Maintenance | No | Add to System Control | Medium | Periodic sync |
| test_mobikwik_bbps_e2e | Deprecated / dev | No | None | Low | E2E test; not production runbook |
| seed_api_products | One-time setup | No | None | Medium | Environment bootstrap |

---

## 2. Scripts (no UI)

| Script | Purpose | Note |
|--------|---------|------|
| pre_deploy_check.sh | Pytest, migrate --check, audit_partners, optional health check | CI/deploy; keep as script |
| fetch_carwale_images.py | Fetch Carwale images | Utility; CLI-only |
| send_parkpe_test_email.py | Send Parkpe test email | Prefer management command; document as legacy |
| start_lan.sh | Start LAN access (dev) | Dev; CLI-only |

---

## 3. System Control UI spec

All commands that **must** appear in Super Admin → System Control (run button, status, logs) are listed below. Each must satisfy the following UI requirements.

### Required UI elements (for every job in System Control)

- **Run button:** Present in System Control job list; triggers run (sync or async per command).
- **Dry-run option:** If the command supports it (e.g. `--dry-run`), expose as checkbox or toggle in the run form. Commands with dry-run: `simulate_vendor_down`, `backup_verify` (if supported).
- **Status indicator:** From SystemJobStatus (last run, OK/FAILED, SLA status). Already in Job History; surface on System Control card/list per job.
- **Last run time:** From SystemJobRun or SystemJobStatus; show on card/list.
- **Execution logs:** Link to Job History run detail; download log via existing job_run_download view.
- **Error report:** Show last run error message (e.g. first 200 chars) on System Control card/list when status is FAILED.
- **Permission control:** Super Admin role only (existing); document required permission.

### Commands that must appear in System Control (after Phase B)

**Already in UI (keep):**

- audit_partners  
- reconcile_daily  
- run_billing_cycle  
- generate_invoices  
- fraud_scan  
- archive_apilog  
- compute_sla  
- compliance_pack  
- enterprise_export  

**Add to System Control:**

- system_watchdog  
- resend_pending_emails  
- fix_stuck_batches  
- process_batch_sync  
- simulate_vendor_down (with dry-run option)  
- backup_verify (with dry-run if supported)  
- sync_api_registry  
- load_bbps_operators (optional; can remain CLI for infrequent use)  

### Backend requirement

Any new command added to the UI must be included in **ALLOWED_COMMANDS** in `api_management.services.command_runner_service` (and any allowlist used by job_run_service) so that runs go through job_run_service and create SystemJobRun + ControlAuditLog.

---

## 4. Commands that remain CLI-only (summary)

| Reason | Commands |
|--------|----------|
| One-time setup | setup_super_admin, setup_roles, create_internal_api_keys, ensure_parkpe_partner, migrate_parkpe_partner, ensure_parkpe_voucher_brand, set_parkpe_default_pg, assign_default_vendors, seed_* (all), mobikwik_bbps_clear_token_cache, seed_api_products |
| Destructive / dev | reset_db, clean_and_seed, seed_data — must not be triggerable from production UI |
| test_* / dev only | test_all_api_responses, test_api_and_check_logs, test_euronet_bbps, test_paypoint_aeps, test_all_bbps_operators, test_mobikwik_bbps, test_voucher_logging, test_all_cashfree_apis, test_notifications, test_all, test_mobikwik_bbps_e2e |
| One-off diagnostic / migration | verify_api_key_autofill, check_ticket_tables, fix_ticket_migration, compare_mobikwik_operators |

*End of Phase B — Command to UI Mapping.*
