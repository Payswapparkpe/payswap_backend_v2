# Phase 0 Audit — Step 4: Command Inventory

**Read-only audit. No code changes.**

---

## 1. Management commands (portal)

| Command | Help (summary) | Related service / model |
|---------|----------------|--------------------------|
| setup_super_admin | Create Super Admin role, sandeepsuda user, demote others | Role, User |
| setup_roles | Setup default roles, groups, permissions | Role |
| compliance_pack | Generate compliance pack (SOC2, ISO, RBI, bank DD) | DB state |
| backup_verify | Verify backup readiness (DB, Redis) | — |
| enterprise_export | Export enterprise data for audit | Reporting, reconciliation |
| simulate_vendor_down | Simulate vendor down (dry-run) | PartnerVendorAssignment |
| run_billing_cycle | Billing cycle: settlements + generate_invoices | Billing, Invoice |
| generate_invoices | Generate partner invoices (GST, Settlement, Commission) | Invoice |
| fraud_scan | Scan for fraud indicators | — |
| reconcile_daily | Daily reconciliation: DB vs wallet ledger | Wallet, ledger |
| audit_partners | Audit partner data (key, subscriptions, vendors, wallet) | ResellerPartner, APIKey |
| create_internal_api_keys | Create API keys for Payswap/Parkpe, assign vendors | APIKey, ResellerPartner |
| ensure_parkpe_partner | Ensure ParkPe ResellerPartner; optional API key, vendors | ResellerPartner |
| migrate_parkpe_partner | ParkPe (and partners) with key, vendors, wallet, subscriptions | ResellerPartner, APIKey, Wallet |
| mobikwik_bbps_clear_token_cache | Clear Mobikwik BBPS token cache | Cache |
| load_bbps_operators | Load BBPS operators from Mobikwik/Operators.xlsx | BBPS operators |
| seed_connect_predefined_messages | Seed Connect predefined chat messages | Connect messages |
| ensure_parkpe_voucher_brand | Ensure ParkPe voucher brand approved/active | Voucher brand |
| set_parkpe_default_pg | ParkPe default Cashfree config | Payment config |
| compare_mobikwik_operators | Compare BBPS operators: DB vs Mobikwik API | BBPS |
| test_all_api_responses | Test all API v2 endpoints | api.v2 |
| verify_api_key_autofill | Verify API key autofill (view/template) | — |
| test_api_and_check_logs | Test API v2 + check API Explorer logs | APILog |
| test_euronet_bbps | Test Euronet BBPS API | Euronet |
| test_paypoint_aeps | Test PayPoint AEPS API | PayPoint |
| assign_default_vendors | Assign default vendors to partners | PartnerVendorAssignment |
| seed_vendor_apis | Seed ApiVendor, VendorApi (Service Flow) | ApiVendor |
| seed_services | Seed initial services | Service |
| resend_pending_emails | Resend PENDING/FAILED emails | Email queue |
| send_parkpe_test_email | Send test email via Parkpe SMTP | Email |
| test_all_bbps_operators | Test all BBPS operators from Operators.xlsx | BBPS |
| test_mobikwik_bbps | Test Mobikwik BBPS API | Mobikwik |
| seed_payment_services | Seed payment services (AEPS, DMT, BBPS) | Service |
| fix_stuck_batches | Fix stuck voucher batches (PROCESSING) | Batch |
| process_batch_sync | Process voucher batch synchronously | Batch |
| test_voucher_logging | Test voucher logging | Voucher |
| test_all_cashfree_apis | Test Cashfree APIs + logging | Cashfree |
| check_ticket_tables | Check ticket tables/indexes | Ticket |
| fix_ticket_migration | Drop conflicting ticket indexes | Ticket |
| seed_data | Seed default data (deletes existing) | Multiple |
| clean_and_seed | Clean DB, migrate, setup_roles, seed | Multiple |
| reset_db | Reset DB (drop/recreate) | — |
| test_notifications | Test SMS and Email | Notifications |
| test_all | Test all functionality | — |

---

## 2. Management commands (api_management)

| Command | Help (summary) | Related service / model |
|---------|----------------|--------------------------|
| compute_sla | Compute SLA stats from APILog per partner/service/date | APILog, SystemJobStatus |
| system_watchdog | Evaluate SLA for SystemJobStatus (RED/ORANGE/etc.) | SystemJobStatus |
| archive_apilog | Archive APILog older than N days to CSV, delete | APILog |
| test_mobikwik_bbps_e2e | E2E: Mobikwik BBPS for Parkpe | BBPS |
| seed_api_products | Seed APIProduct (Parkpe, Payswap) | APIProduct |
| sync_api_registry | Sync APIRegistry from URL config | APIRegistry |

---

## 3. Scripts (scripts/)

| Script | Purpose |
|--------|---------|
| pre_deploy_check.sh | Pytest (selected tests), migrate --check, audit_partners, optional HEALTH_CHECK_URL |
| fetch_carwale_images.py | Fetch Carwale images (utility) |
| send_parkpe_test_email.py | Send Parkpe test email (standalone) |
| start_lan.sh | Start LAN access (dev) |

---

## 4. Commands: UI Exists? and Risk (summary)

| Command | Purpose | Related service | UI exists? | Risk |
|---------|---------|-----------------|------------|------|
| audit_partners, reconcile_daily, run_billing_cycle, generate_invoices, fraud_scan, archive_apilog, compute_sla, compliance_pack, enterprise_export | See §1–2 | See §1–2 | **Yes** (Super Admin System Control / internal run-job) | Low (audited) |
| setup_super_admin, setup_roles | One-time setup | Role, User | No | Low (run once) |
| load_bbps_operators, seed_*, assign_default_vendors, ensure_parkpe_partner, migrate_parkpe_partner, create_internal_api_keys | Setup / seeding | Various | No | Medium (manual/cron) |
| backup_verify, simulate_vendor_down, resend_pending_emails, fix_stuck_batches, process_batch_sync | Ops | Various | No | Medium (ops only) |
| system_watchdog, sync_api_registry, seed_api_products | Governance / sync | api_management | No | Medium (cron/setup) |
| test_* (all test_* commands) | Dev / verification | Various | No | Low (dev only) |
| reset_db, clean_and_seed, seed_data | Dev / reset | Multiple | No | **High** (destructive) |
| fix_ticket_migration, verify_api_key_autofill | One-off / diagnostic | Ticket, view | No | Low (one-off) |

---

## 5. Overlap with UI (Super Admin System Control)

These commands can be run from **Super Admin → System Control** (and optionally **Internal API** POST `/internal/run-job/`):

- audit_partners  
- reconcile_daily  
- run_billing_cycle  
- generate_invoices  
- fraud_scan  
- archive_apilog  
- compute_sla  
- compliance_pack  
- enterprise_export  

So **9 commands** have a UI trigger; all others are CLI-only (or invoked by cron/scripts).

---

## 6. Commands with no UI

All management commands except the 9 above have **no** UI button in the portal. Examples:

- setup_super_admin, setup_roles — one-time setup.  
- backup_verify, simulate_vendor_down — ops.  
- ensure_parkpe_partner, migrate_parkpe_partner, create_internal_api_keys — setup/ops.  
- load_bbps_operators, seed_*, assign_default_vendors — seeding/setup.  
- test_* (test_all_api_responses, test_mobikwik_bbps, etc.) — dev/testing.  
- fix_stuck_batches, process_batch_sync, resend_pending_emails — ops.  
- system_watchdog, sync_api_registry, seed_api_products — governance/setup.  
- reset_db, clean_and_seed, seed_data — dev/reset.

---

## 7. Possibly deprecated or one-off

- **reset_db**, **clean_and_seed**, **seed_data** — destructive; typically dev only.  
- **fix_ticket_migration** — migration fix; one-off.  
- **test_*** — many test commands (test_euronet_bbps, test_paypoint_aeps, test_all, etc.); not production runbooks.  
- **verify_api_key_autofill** — diagnostic.  
- **send_parkpe_test_email**, **scripts/send_parkpe_test_email.py** — duplicate capability (command vs script).

---

*End of Step 4 — Command Inventory.*
