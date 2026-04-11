# Security Remediation Report

**Project:** Payswap  
**Prepared on:** April 11, 2026  
**Prepared for:** Cursor-assisted remediation

---

## 1) Executive Summary

This report identifies security weaknesses found in the current codebase and describes **exactly what must be changed**, **why it is required**, and **how to implement each fix safely** without regressions.

Top mandatory fixes:

1. Open redirect via unvalidated `next` parameters.
2. Open redirect via unvalidated `HTTP_REFERER`.
3. Weak password policy in public registration.
4. Public direct registration endpoint bypassing OTP flow.

Additional hardening:

- OAEP with SHA-1 (legacy crypto primitive) should be upgraded if vendor-compatible.

---

## 2) Audit Scope and Constraints

### Scope reviewed

- Django backend security posture.
- API auth/session/csrf behavior.
- Redirect safety.
- Password policy enforcement.
- Cryptographic usage patterns.

### Tooling/validation constraints during this review

- Dependency CVE scans could not complete in this environment due to DNS/network restrictions.
  - `pip-audit` could not reach `pypi.org`.
  - `npm audit` could not reach `registry.npmjs.org`.

> Cursor should rerun dependency audits in an internet-enabled environment.

---

## 3) Findings and Required Changes

## SEC-001 — Open Redirect via `next` Parameter (**Medium**, mandatory)

### Affected files

- `portal/views/legacy.py:1295`
- `portal/views/legacy.py:1330`
- `portal/views/legacy.py:1412`
- `portal/views/legacy.py:1435`
- `portal/views/legacy.py:1450`

### Why this is required

Untrusted `next` values are passed to redirects without host/scheme validation. Attackers can supply external URLs, causing phishing/open-redirect abuse.

### Required remediation

1. Add a reusable safe-redirect helper in `portal/views/legacy.py`:
   - Input: `request`, `next_url`, fallback path.
   - Use Django `url_has_allowed_host_and_scheme`.
   - Only allow relative URLs or same-host absolute URLs.
   - Reject protocol-relative URLs (`//evil.com`).
2. Replace every direct `request.GET.get('next', ...)` redirect usage with helper output.

### Implementation guidance (important)

- Keep legit internal values like `/dashboard/`, `/auth/unlock-with-pin/?next=%2Fdashboard%2F` working.
- If invalid, always fallback to `/dashboard/`.
- Do not remove `next` support entirely; sanitize it.

### Minimum test cases

- `next=/dashboard/` -> allowed.
- `next=https://evil.example` -> blocked/fallback.
- `next=//evil.example` -> blocked/fallback.
- `next=/dashboard/?tab=profile` -> allowed.

---

## SEC-002 — Open Redirect via `HTTP_REFERER` (**Low-Medium**, mandatory)

### Affected file

- `portal/views/log_views.py:473`

### Why this is required

`HTTP_REFERER` is client-controlled and spoofable. Redirecting to it without validation allows external redirect abuse.

### Required remediation

1. Validate referer using `url_has_allowed_host_and_scheme`.
2. If safe and same-host, extract `path + query` and redirect there.
3. Else fallback to `/logs/`.

### Implementation guidance

- Accept no host or current host only.
- Never redirect directly to a full external URL.

### Minimum test cases

- Same-origin referer -> redirect allowed.
- External referer -> fallback to `/logs/`.
- Missing referer -> fallback to `/logs/`.

---

## SEC-003 — Weak Password Validation in Registration (**Medium**, mandatory)

### Affected file

- `api/auth_parkpe/views.py:311`

### Why this is required

Current check only enforces minimum length (`>=6`) and bypasses Django password validators configured in settings. This allows weak passwords and inconsistent policy enforcement.

### Required remediation

1. In `_validate_register_payload`, use Django validator pipeline:
   - `django.contrib.auth.password_validation.validate_password(password)`
2. Catch `ValidationError` and return user-friendly error in API response.
3. Remove or replace the hardcoded 6-character rule.

### Implementation guidance

- Keep response contract stable (`{"message": "...", "userId": ""}` style).
- Use validator messages instead of inventing weaker custom rules.

### Minimum test cases

- Weak password like `123456` -> rejected.
- Password similar to email/username -> rejected.
- Strong password -> accepted.

---

## SEC-004 — Public Registration Endpoint Bypasses OTP Flow (**Medium**, strongly recommended)

### Affected file

- `api/auth_parkpe/views.py:532`

### Why this is required

`AuthRegisterView` allows direct account creation without OTP verification, while OTP-based registration already exists. This weakens identity assurance and abuse controls.

### Required remediation (preferred)

1. Deprecate direct register endpoint.
2. Return clear response instructing clients to use:
   - `POST /api/auth/register/send-otp`
   - `POST /api/auth/register/verify`

### Alternate remediation (if endpoint must stay)

- Convert endpoint to OTP-initiation only; do not create user until OTP verify succeeds.

### Implementation guidance

- Coordinate with frontend before hard cutover.
- If deprecating, return stable code/message so client can migrate safely.

### Minimum test cases

- Direct register call no longer creates user without OTP.
- OTP flow still creates user successfully.

---

## SEC-005 — OAEP SHA-1 Usage in Cashfree Signature Paths (**Low-Medium**, hardening)

### Affected files

- `portal/services/vendors/cashfree.py:130`
- `portal/services/cashfree_vehicle_rc.py:71`

### Why this is required

SHA-1 is a legacy hash and often fails modern compliance/security standards, even when used in OAEP contexts.

### Required remediation

1. Confirm Cashfree compatibility for OAEP SHA-256.
2. If supported, migrate:
   - `padding.MGF1(algorithm=hashes.SHA256())`
   - `algorithm=hashes.SHA256()`
3. If not supported by vendor, document risk acceptance with explicit vendor dependency note.

### Implementation guidance

- Do not change silently in production without integration testing.
- Coordinate rollout with sandbox/UAT verification.

---

## 4) Implementation Guardrails for Cursor (Do/Don’t)

### Do

- Use Django-native URL safety checks (`url_has_allowed_host_and_scheme`).
- Centralize redirect sanitization into helper(s), then reuse.
- Preserve valid internal navigation behavior.
- Keep API response shapes backward-compatible unless intentionally deprecating.
- Add focused tests for each remediation.

### Don’t

- Don’t trust `HTTP_REFERER` or raw `next` directly.
- Don’t remove internal redirect functionality entirely.
- Don’t keep both weak custom password rules and Django validators in conflict.
- Don’t deploy crypto algorithm changes without vendor compatibility proof.

---

## 5) Validation Checklist (Cursor must run)

## A) Security/system checks

- `python3 manage.py check --deploy`

## B) Tests for remediations

- Redirect sanitization tests (`next`, referer).
- Registration password validation tests.
- Registration flow tests (direct register vs OTP flow behavior).

## C) Dependency vulnerability scans (internet required)

- `python3 -m pip_audit -r requirements.txt`
- `npm audit --audit-level=moderate` (run in `frontend/`)

---

## 6) Suggested Remediation Order

1. SEC-001 (`next` redirect sanitization)
2. SEC-002 (referer redirect sanitization)
3. SEC-003 (password validator integration)
4. SEC-004 (deprecate/bypass-proof direct register)
5. SEC-005 (crypto hardening with vendor confirmation)

---

## 7) Definition of Done

This report is considered fully remediated when:

- All mandatory issues (SEC-001, SEC-002, SEC-003) are fixed and tested.
- SEC-004 is either deprecated or functionally enforced through OTP-only completion.
- SEC-005 is either upgraded to SHA-256 or documented as accepted vendor-constrained risk.
- `manage.py check --deploy` shows no related unresolved security warnings for these areas.
- Dependency audit results are attached from an internet-enabled environment.

