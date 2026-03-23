# Phase 0 Audit — Step 5: Service & Business Logic Map

**Read-only audit. No code changes.**

---

## 1. Services by directory

### 1.1 portal/services/

| Service | Purpose (inferred) |
|---------|--------------------|
| api_key_service | API key CRUD, hashing; ResellerPartner, APIKey |
| approval_service | Approval requests; uses PartnerAccountingService |
| bbps_operators_loader | Load BBPS operators (e.g. from file) |
| bbps_service | BBPS orchestration; MobikwikBBPSClient, EuronetBBPSClient |
| billing_service | Billing cycle, settlements, invoices; ResellerPartner, ResellerPartnerSettlement/Transaction |
| brand_onboarding_service | GiftVoucherBrand onboarding |
| bulk_voucher_service | Bulk voucher issuance; VoucherClientService, voucher_utils |
| cashfree_vehicle_rc | Cashfree vehicle RC (e.g. fetch RC) |
| dmt_service | DMT flows; PayPointDMTClient |
| aeps_service | AEPS flows; PayPointAEPSClient |
| email_queue_service | Email send (SMTP); EmailQueue |
| execution_engine | Handler registry, execution (e.g. AEPS/DMT steps) |
| handler_registry | Register step handlers (paypoint, paypoint_dmt) |
| idempotency_service | IdempotencyRecord |
| kyc_service | KYC CRUD |
| notification_service_v2 | Notifications (SMS, email); uses portal.tasks.notification_tasks |
| partner_accounting_service | Partner accounting (transactions, pricing) |
| partner_margin_service | Partner margins; ResellerPartnerTransaction, ResellerPartnerPricing |
| partner_vendor_service | PartnerVendorAssignment; cache, ResellerPartner, ApiVendor |
| parkpe_voucherx_bridge | ParkPe ↔ VoucherX bridge; GiftVoucher, VoucherService |
| pincode_service | Pincode lookup (external API) |
| reseller_service | ResellerPartner, Wallet |
| service_management_service | Service, ServiceCost |
| storage_service | File storage; AWSS3Client |
| ticket_service | Ticket, TicketNote, TicketAttachment, etc. |
| verification_api | Verification (e.g. Cashfree); VerificationAPIService |
| voucher_service | Voucher lifecycle; VoucherClientService, VoucherOTPService, voucher_utils |
| voucher_client_service | VoucherClient |
| voucher_export_service | Voucher export (CSV) |
| voucher_otp_service | GiftVoucherOTP; NotificationServiceV2 |
| voucherx_service | VoucherX metrics/dashboard |
| wallet_service | Wallet, WalletTransaction |
| growth_metrics | Growth metrics; ResellerPartner, ResellerPartnerTransaction/Settlement |
| postman_sync | Postman sync (API Explorer) |
| agent_service, department_service | Agent, Department (tickets) |

**portal/services/vendors/**  
mobikwik, cashfree_pg, kaleyra, cashfree, euronet, paypoint, paypoint_dmt, instantpay, leegality, invincible_ocean, aws_s3, aws_sns, aws_ses — vendor-specific API clients.

### 1.2 api_management/services/

| Service | Purpose |
|---------|---------|
| command_runner_service | run_management_command (ALLOWED_COMMANDS); call_command, capture output |
| job_run_service | run_command_with_logging; SystemJobRun, sync/async (Celery) |
| control_tower_health | get_health_summary, get_celery_summary; cache 60s; uses api.internal.views.get_health_payload |
| system_job_service | record_job_run, compute_sla_status, SLA rules; SystemJobStatus |
| operational_metrics | (metrics for dashboard) |
| business_metrics | (metrics) |
| financial_metrics | (metrics) |
| technical_metrics | (metrics) |

**api_management (root):** control_audit_service (log_control_action, get_client_ip, sanitize audit values); ControlAuditLog.

---

## 2. Core flows

| Flow | Entry | Services / commands | Exit |
|------|--------|---------------------|------|
| **Billing** | Cron or Super Admin (run_billing_cycle) | run_billing_cycle → billing_service; generate_invoices → billing_service, templates | Settlements, invoices (PDF), DB |
| **Auth** | Portal signin/signup, API auth | otp_service, notification_service_v2, MFA (User), allauth | Session, JWT |
| **Governance** | UI (control tower, super admin), API /api/control/* | control_tower_health, api.governance.views_control; kill switch (cache), feature flags; control_audit_service | Redis (kill switch), DB (FeatureFlag), ControlAuditLog |
| **Settlement** | run_billing_cycle, admin partner settlement | billing_service, partner_accounting_service, ResellerPartnerSettlement | DB, PDF |
| **SLA** | compute_sla command, system_watchdog | system_job_service (record_job_run from commands), compute_sla (APILog), system_watchdog (SystemJobStatus.sla_status) | SystemJobStatus, APILog |
| **Fraud** | fraud_scan command | fraud_scan (portal.management.commands) — scan indicators | Report / logs |
| **Super Admin job run** | UI System Control, POST /internal/run-job/ | job_run_service.run_command_with_logging → command_runner_service or Celery; SystemJobRun; control_audit_service | SystemJobRun, ControlAuditLog |

---

## 3. Dependencies (selected)

- **billing_service** → ResellerPartner, ResellerPartnerSettlement, ResellerPartnerTransaction; templates.  
- **voucher_service** → VoucherClientService, VoucherOTPService, voucher_utils, voucher_logging.  
- **partner_accounting_service** → ResellerPartner, transactions, pricing.  
- **approval_service** → PartnerAccountingService.  
- **otp_service** → NotificationServiceV2, cache, mfa_utils, phone_utils; can enqueue otp_dual_delivery_task.  
- **job_run_service** → command_runner_service (ALLOWED_COMMANDS), SystemJobRun; Celery task run_management_command_async.  
- **control_tower_health** → get_health_payload (api.internal.views), get_celery_summary; cache.  
- **system_job_service** → SystemJobStatus; used by instrumented commands (audit_partners, reconcile_daily, etc.).  
- **bbps_service** → MobikwikBBPSClient, EuronetBBPSClient.  
- **partner_vendor_service** → cache, ResellerPartner, ApiVendor, PartnerVendorAssignment.

---

## 4. Duplicated logic (findings)

- **Run command:** Two entry points — (1) Super Admin “System” run_command (SuperAdminRunCommandView → command_runner_service, no SystemJobRun), (2) Super Admin “System Control” run_job (SuperAdminRunJobView → job_run_service, creates SystemJobRun). Same ALLOWED_COMMANDS; one records per-run in DB, one does not.  
- **Health:** get_health_payload in api.internal.views; control_tower_health.get_health_summary calls it and adds Celery. Used by Control Tower UI, Super Admin system page, Health Center — single implementation but multiple consumers.  
- **Kill switch:** Toggled from Governance emergency (portal + API) and Super Admin emergency; both write to same cache key (GOV_KILL_SWITCH_CACHE_KEY) — logic not duplicated but two UIs.  
- **Partner vendor assignment:** partner_vendor_service (portal); API governance has partner subscriptions/limits. Partner “vendor” concept in portal vs API control — different layers (assignment vs subscription toggle).  
- **Send email:** email_queue_service (portal), notification_service_v2 (portal), send_mail in various places; resend_pending_emails command. Multiple paths to send email (queue vs direct vs task).

---

*End of Step 5 — Service Map.*
