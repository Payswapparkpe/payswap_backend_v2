# Phase 0 Audit — Step 8: Test Coverage Map

**Read-only audit. No code changes.**

---

## 1. Test files and targets

### 1.1 api/tests/

| File | Test classes / targets |
|------|------------------------|
| test_analytics.py | TestAnalyticsDashboard, TestEnterpriseAPI — analytics dashboard and enterprise API |
| test_production_smoke.py | TestProductionSmoke, TestProductionSmokeWithPartner — smoke (health, auth) |
| test_partner_governance.py | TestParkPeRequiresKey, TestSubscriptionEnforcement, TestInternalBypassBlocked — partner API key and subscription enforcement |
| test_governance_control.py | TestGovernanceDashboard, TestGovernanceControlAPIs, TestGovernanceKillSwitch, TestGovernanceRBAC, TestAggregationServices — governance UI and APIs, kill switch, RBAC |
| test_v2_voucher_partner_scope.py | TestV2VoucherPartnerScope — v2 voucher partner scope |
| test_v2_api.py | TestV2PublicEndpoints, TestV2PartnerEndpoints — v2 public and partner endpoints |
| test_v1_api.py | TestV1Health — v1 health |
| conftest.py | Pytest fixtures (no test classes) |

### 1.2 portal/tests/

| File | Test classes / targets |
|------|------------------------|
| test_super_admin_system_control.py | SuperAdminSystemControlAccessTest (system_control view access), SuperAdminJobRunLoggedTest (job run creates SystemJobRun + audit), SuperAdminHealthCenterTest (health center 200) |
| test_api_responses.py | APIResponseTests — request_id, response_id, standard/error format |
| test_otp_lockout.py | OTPLockoutTests — lockout after max failures, success resets |
| test_otp_dual_delivery.py | OTPDualDeliveryTests — dual delivery, storage, verification, task structure |
| test_voucher_service.py | TestVoucherServiceValidation, TestVoucherServiceIssuance — voucher_service validation and issuance |
| test_partner_accounting_service.py | TestResellerPartnerPricingCalculation, TestPartnerAccountingCharge — partner_accounting_service pricing and charge |
| test_wallet_service.py | TestWalletServiceDebit, TestWalletServiceBoundaryAndConcurrency — wallet_service debit, boundaries, concurrency |
| test_execution_engine.py | TestServiceExecutionEngine — execution_engine (handlers, steps, context) |
| test_logging.py | LoggingTests — get_client_ip, user_agent, session_id, log categorization, write_logs_task |
| test_user_manager.py | UserManagerTests — create_superuser/create_user, role, username generation |
| test_profile_completion.py | ProfileCompletionTests — profile completion required, social signup, form, middleware redirect |
| test_authentication.py | AuthenticationTestCase (base), MultiStepLoginTests, MultiStepSignupTests, SocialAuthenticationTests, ProfileCompletionTests, IPLoggingTests, MFATests, SuperuserCreationTests, RateLimitingTests, AccountLockoutTests — login, signup, OTP, lockout, MFA, IP logging |
| test_settings.py | No test classes — TEST_SETTINGS override only (used by other tests) |
| fixtures.py | Factory classes (Role, User, Profile, GiftVoucher*, Wallet, Ticket, etc.) — not tests |

### 1.3 api_management/

- No dedicated `api_management/tests/` package found.
- `api_management/management/commands/test_mobikwik_bbps_e2e.py` is a management command (e2e runner), not a unit test module.

---

## 2. Coverage by area

| Area | api/tests | portal/tests | Notes |
|------|-----------|--------------|--------|
| Auth (login, signup, OTP, MFA, lockout) | — | Yes (test_authentication, test_otp_*, test_user_manager, test_profile_completion) | Strong in portal |
| Governance (dashboard, APIs, kill switch, RBAC) | Yes (test_governance_control) | — | API governance covered |
| Partner (subscription, API key, accounting) | Yes (test_partner_governance) | Yes (test_partner_accounting_service) | Both API and service |
| Super Admin (system control, job run, health) | — | Yes (test_super_admin_system_control) | Access and job run audit |
| Voucher (service, partner scope) | Yes (test_v2_voucher_partner_scope) | Yes (test_voucher_service) | Service + API scope |
| Wallet | — | Yes (test_wallet_service) | Service only |
| Execution engine (AEPS/DMT steps) | — | Yes (test_execution_engine) | Portal only |
| API responses (request_id, format) | — | Yes (test_api_responses) | Portal |
| Logging (IP, categorization, task) | — | Yes (test_logging) | Portal |
| Analytics / enterprise API | Yes (test_analytics) | — | API only |
| Health / smoke | Yes (test_v1_api, test_production_smoke) | — | API only |
| Billing / run_billing_cycle / invoices | — | No | No tests found |
| Connect (RC, chat, scan) | — | No | No tests found |
| BBPS (Mobikwik, Euronet) | — | No | Only e2e command, no unit tests |
| api_management (job_run_service, system_job_service, control_audit) | — | No | No dedicated tests |
| Portal views (dashboard, reseller, voucherx, tickets) | — | No | No view tests beyond auth/super_admin |

---

## 3. Gaps

- **Billing:** No tests for billing_service, run_billing_cycle, generate_invoices, or settlement flow.
- **Connect:** No tests for connect views, RC fetch, chat, or connect services.
- **BBPS:** No unit tests for bbps_service or vendor clients; only test_mobikwik_bbps_e2e command.
- **api_management services:** command_runner_service, job_run_service, system_job_service, control_audit_service, control_tower_health not covered by dedicated tests (Super Admin job run is tested from portal side).
- **Portal views:** Most portal views (dashboard, voucherx, reseller, partner console, governance Django views beyond those hit by API tests) have no direct test; governance is covered via API tests (test_governance_control).
- **Middleware:** Only logging and profile-completion middleware referenced in tests; no broad middleware tests.
- **Celery tasks:** write_logs_task structure only; other tasks (notification_tasks, otp_dual_delivery_task, etc.) not systematically tested.

---

## 4. Duplicate tests

- **Superuser creation / profile:** test_user_manager (create_superuser_auto_assigns_super_role, creates_profile, auto_generates_username) and test_authentication (SuperuserCreationTests with same three behaviors). Overlap: superuser creation and profile creation tested in both.
- **Profile completion:** test_profile_completion.py (ProfileCompletionTests) and test_authentication.py (ProfileCompletionTests under AuthenticationTestCase). Overlap: profile completion required, form, middleware.
- **OTP lockout:** test_otp_lockout.py (OTPLockoutTests) and test_authentication.py (AccountLockoutTests, test_account_locks_after_10_failed_attempts, etc.). Different layers (OTP vs login attempt lockout) but similar “lockout after N failures” behavior in two files.

---

*End of Step 8 — Test Coverage Map.*
