# Phase 11 — End-to-End Test Report

**Audit mode: no code changes. This report documents test run results only.**

---

## 1. Test run summary

| Suite | Collected | Passed | Failed | Skipped | Errors |
|-------|-----------|--------|--------|---------|--------|
| **api/tests** | 42 | 40 | 0 | 2 | 0 |
| **portal/tests** | 90 | ~74 | ~12+ | 0 | ~4* |
| **Total** | 132 | ~114 | ~12+ | 2 | ~4 |

\* Portal run: some tests reported as Error (E) in a short run (e.g. test_api_responses.py EEEE), likely setup/import; full run was not completed to final count. Failed (F) count is from observed output.

**Environment:** Django 5.2.10, pytest 9.0.2, Python 3.14.2, settings from pytest.ini (core.settings). Test DB: default alias.

---

## 2. By suite / area

### 2.1 Production smoke (api/tests/test_production_smoke.py)

| Result | Count |
|--------|--------|
| Passed | 12 |
| Skipped | 1 (TestProductionSmokeWithPartner::test_connect_with_valid_key_returns_not_403_forbidden) |
| Failed | 0 |

**Passed:** internal health 200, DB ok, API key required for connect/bbps/payment, kill switch read/write, audit log model, partner subscription model, reseller partner model, API key model.

### 2.2 Governance (api/tests/test_governance_control.py)

| Result | Count |
|--------|--------|
| Passed | 10 |
| Skipped | 1 (TestGovernanceControlAPIs::test_control_api_toggle_creates_audit) |
| Failed | 0 |

**Passed:** dashboard overview auth, control APIs list, kill switch post/disable, RBAC 403, technical/financial metrics services.

### 2.3 Partner (api/tests/test_partner_governance.py)

| Result | Count |
|--------|--------|
| Passed | 7 |
| Failed | 0 |

**Passed:** ParkPe requires key (connect, bbps, payment, voucher 403 without key), subscription denied/allowed, internal bypass blocked.

### 2.4 Analytics / enterprise (api/tests/test_analytics.py)

| Result | Count |
|--------|--------|
| Passed | 7 |
| Failed | 0 |

### 2.5 V1 / V2 API (api/tests/test_v1_api.py, test_v2_api.py, test_v2_voucher_partner_scope.py)

| Result | Count |
|--------|--------|
| Passed | 6 |
| Failed | 0 |

**Passed:** v1 health 403/200, v2 health, public endpoint, partner 401/200 with API key/Bearer, voucher partner scope isolation.

### 2.6 Portal — authentication, profile, OTP, super_admin, wallet, voucher, etc.

From partial run (portal/tests):

| Area | Passed | Failed | Notes |
|------|--------|--------|--------|
| API responses | 0 | 0 | 4 Errors (E) in one run — possible fixture/setup |
| Authentication | 18 | 3 | See failed list below |
| Execution engine | 6 | 0 | |
| Logging | 9 | 0 | |
| OTP dual delivery | 2 | 2 | |
| OTP lockout | 2 | 0 | |
| Partner accounting | 7 | 2 | |
| Profile completion | 4 | 1 | |
| Super Admin system control | 5 | 0 | |
| User manager | 5 | 1 | |
| Voucher service | 6 | 1 | |
| Wallet service | 3+ | 0 | (run incomplete) |

---

## 3. Failed tests (portal — observed)

| Test | File | Likely cause |
|------|------|----------------|
| ProfileCompletionTests::test_profile_completion_form_validation | test_authentication.py | TemplateDoesNotExist: portal/profile/complete.html |
| SuperuserCreationTests::test_createsuperuser_creates_profile | test_authentication.py | (not captured) |
| RateLimitingTests::test_otp_rate_limiting | test_authentication.py | (not captured) |
| test_otp_stored_for_both_email_and_phone | test_otp_dual_delivery.py | (not captured) |
| test_otp_verification_from_either_channel | test_otp_dual_delivery.py | (not captured) |
| TestResellerPartnerPricingCalculation::test_tiered_pricing_percentage | test_partner_accounting_service.py | (not captured) |
| TestPartnerAccountingCharge::test_idempotent_charge_duplicate_reference_id | test_partner_accounting_service.py | (not captured) |
| ProfileCompletionTests::test_profile_completion_saves_data | test_profile_completion.py | (not captured) |
| UserManagerTests::test_create_superuser_creates_profile | test_user_manager.py | (not captured) |
| TestVoucherServiceIssuance::test_issue_single_voucher_returns_voucher_code_and_pin | test_voucher_service.py | (not captured) |

**Note:** Audit rules: no fixes. These are documented for later cleanup.

---

## 4. Skipped tests

| Test | Reason (if known) |
|------|--------------------|
| TestGovernanceControlAPIs::test_control_api_toggle_creates_audit | (pytest skip) |
| TestProductionSmokeWithPartner::test_connect_with_valid_key_returns_not_403_forbidden | (pytest skip) |

---

## 5. Flaky

Not assessed (single run per suite). No flakiness analysis performed.

---

## 6. Billing / SLA–specific tests

- **Billing:** No dedicated billing or run_billing_cycle tests in api/tests or portal/tests (see test_coverage.md). So “billing tests” = none run.
- **SLA:** api_management has compute_sla and system_watchdog commands; no SLA unit tests were run (no such tests in collected 132).

---

## 7. Commands used

```bash
# API tests only (completed)
pytest api/tests -v --tb=no --no-cov -q

# Portal tests (partial / long-running)
pytest portal/tests api/tests -v --tb=short --no-cov
```

---

**End of Phase 11 — E2E Test Report.** No fixes applied; findings only.
