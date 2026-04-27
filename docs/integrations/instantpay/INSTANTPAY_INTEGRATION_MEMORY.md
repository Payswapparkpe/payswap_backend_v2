# InstantPay Integration Memory

This file tracks ongoing InstantPay vehicle challan integration status, decisions, and evidence.
Keep updating this file until integration is fully closed.

## Scope

- Flow: ParkPe Challan Search -> InstantPay `/identity/vehicleChallan`
- Primary blocker: vendor returns `RPI` with `The X-Ipay-Auth-Code header is invalid.`

## Documentation Baseline

- Overview: https://developers.instantpay.in/reference/overview
- API Protocols: https://developers.instantpay.in/reference/api-protocols
- Testing Credentials: https://developers.instantpay.in/reference/testing-credentials
- Credential onboarding: https://developers.instantpay.in/docs/how-can-i-get-the-credentials-for-the-apis
- API testing guide: https://developers.instantpay.in/docs/how-do-i-test-the-apis
- Identity examples:
  - https://developers.instantpay.in/reference/identity-verification-fssai-verification
  - https://developers.instantpay.in/reference/identity-verification-tan-verification

## Current Runtime Contract (implemented)

- Config knob: `INSTANTPAY_IDENTITY_AUTH_MODE`
  - Supported: `sha256_pipe`, `sha256_concat`, `static`, `base64_basic`
  - Default: `sha256_pipe`
- Identity request payload is plain JSON:
  - `{"vehicleNumber":"<UPPERCASE_REG_NO>"}`
- Identity headers include:
  - `Content-Type`
  - `X-Ipay-Auth-Code`
  - `X-Ipay-Timestamp`
  - Optional: `X-Ipay-Endpoint-Ip`
- Sanitized request diagnostics are logged under `request_meta`:
  - `auth_mode`, `timestamp_sent`, `auth_code_sha256`, `auth_code_prefix`, `auth_code_suffix`, `header_names`, `normalized_payload`

## Files of Record

- `backend/core/config.py`
- `.env.example`
- `backend/portal/services/vendors/instantpay.py`
- `backend/api/parkpe_logging.py`
- `backend/portal/management/commands/debug_instantpay_identity_auth.py`
- `backend/portal/tests/test_instantpay_client.py`

## Known Latest Evidence

- Logs prove requests reach InstantPay endpoint and include normalized payload + auth metadata.
- Vendor still responds with invalid auth code for current account/path.
- This indicates credential/signature mismatch at vendor-account contract level rather than transport/route/payload shape.

## Hypothesis Matrix

1. InstantPay tenant expects auth mode different from current default (`sha256_pipe`).
2. Account/environment credentials are mismatched (sandbox/prod pair, rotated client secret).
3. Endpoint IP allowlisting or account mapping affects auth acceptance.
4. Vendor may require static module auth code for this identity API in this tenant.

## Next Actions Queue

1. Validate non-E2E checks on every auth-mode/config change.
2. Coordinate vendor confirmation for exact signing formula and required headers for this tenant.
3. If vendor confirms different formula, add new strategy mode in `InstantpayClient` and keep fallback behavior config-driven.
4. Record each attempt with trace ID and mode used.

## Attempt Ledger

- Placeholder (add one row per attempt):
  - Timestamp:
  - Request Trace:
  - Auth Mode:
  - Vendor Response:
  - Outcome:
- Timestamp: 2026-04-27 14:12 IST
  - Request Trace: local debug command `debug_instantpay_identity_auth`
  - Auth Mode: `static` (from `.env`)
  - Vendor Response: not called (dry-run only)
  - Outcome: header generation confirmed with `auth_mode=static`, payload normalized to uppercase string

## Verification Log (Non-E2E)

- 2026-04-27
  - `python -m py_compile core/config.py portal/services/vendors/instantpay.py api/parkpe_logging.py portal/management/commands/debug_instantpay_identity_auth.py portal/tests/test_instantpay_client.py`
    - Result: pass
  - `pytest -q portal/tests/test_instantpay_client.py portal/tests/test_instantpay_hub_service.py`
    - Result: pass (`6 passed`)
  - `ReadLints` on changed InstantPay/config/log/test files
    - Result: no linter errors

## Latest Runtime Evidence Snapshot

- Trace: `46c9abd7-85a3-4ebb-a264-db6d89364e42`
- InstantPay log shows sanitized metadata:
  - `auth_mode: sha256_pipe`
  - `header_names: [Content-Type, X-Ipay-Auth-Code, X-Ipay-Endpoint-Ip, X-Ipay-Timestamp]`
  - `normalized_payload: {vehicleNumber: 24BH8017B}`
- Vendor response still:
  - `statuscode: RPI`
  - `status: The X-Ipay-Auth-Code header is invalid.`

## Doc Alignment Update (Vehicle Challan)

- Source-of-truth contract updated from InstantPay Vehicle Challan page:
  - Required headers: `X-Ipay-Auth-Code`, `X-Ipay-Client-Id`, `X-Ipay-Client-Secret`, `X-Ipay-Endpoint-Ip`
  - `X-Ipay-Auth-Code` can be fixed as `"1"` for this API (mode: `fixed_1`)
  - Body fields: `vehicleRegistrationNumber`, `consent`, `latitude`, `longitude`, `externalRef`
- Code updated to map this exact request shape for `vehicle_challan_lookup`.

## Challan Cache + Refresh (2026-04-27)

- Added DB cache model: `ParkPeChallanRecord` (migration `0084_parkpe_challan_record`)
- Search flow:
  - `GET /api/challan/search` now serves cached challans first (no repeated vendor call)
  - `GET /api/challan/search?...&refresh=1` forces InstantPay sync, updates existing challans, and inserts new challans
- Detail flow:
  - Serves cached row directly for non-pending challans
  - For pending challans, triggers vendor re-sync to catch paid-status transitions and updates cache
- Frontend:
  - Added `Refresh Challans` button on challan search panel
  - `searchChallans` supports `forceRefresh` -> query param `refresh=1`
