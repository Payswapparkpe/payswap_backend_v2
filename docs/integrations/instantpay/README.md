# Instantpay Integration Blueprint

This document defines how Instantpay modules are integrated into Payswap Hub (`/api/v2`) for partner-facing APIs.

## Scope

Business modules requested:

1. AEPS
2. DMT
3. Credit Card Bill Payment
4. RC Verification
5. Vehicle Challan Lookup
6. Account Statement
7. Balance Check
8. Remittance (Domestic)
9. Remittance (Nepal)
10. DigiLocker
11. Card BIN Lookup
12. Credit Report
13. Credit Score Simulator
14. Merchant Onboarding
15. Transaction Status

## Hub Integration Principles

- Partner app calls only Hub APIs (`/api/v2/...`), not Instantpay directly.
- Vendor selection is controlled by `VendorRouter` and partner assignments.
- Instantpay request/response mapping is normalized into a common Hub response envelope.
- Idempotency key is mandatory for transaction-initiation endpoints.
- Every Instantpay call stores transaction/audit metadata for traceability and reconciliation.

## Service Grouping in Hub

- `aeps`: AEPS + balance + statement
- `dmt`: DMT + domestic + nepal remittance
- `billpay`: credit card bill payment
- `vehicle`: RC verify + challan lookup
- `identity_docs`: DigiLocker flows
- `cards`: BIN lookup
- `credit`: report + score simulator
- `merchant`: merchant onboarding
- `reconciliation`: transaction status

## API Surface

All partner APIs live in API v2 and follow:

- `authentication_classes = [APIKeyAuthentication]`
- `permission_classes` include `HasAPIKey`, `HasServicePermission`, `HasVendorAccess`
- request throttling via API key throttles
- standardized JSON response (`success`, `message`, `data`, `errors`)

## Environment & Credentials

Required env keys:

- `INSTANTPAY_CLIENT_ID`
- `INSTANTPAY_CLIENT_SECRET`
- `INSTANTPAY_ENCRYPTION_KEY`
- `INSTANTPAY_ENVIRONMENT` (`SANDBOX` or `PRODUCTION`)
- `INSTANTPAY_BASE_URL` (optional override)

Do not store secrets in docs, code, tests, or Postman collections.

## Related Docs

- `docs/integrations/instantpay/auth-signing-encryption.md`
- `docs/integrations/instantpay/endpoint-matrix.md`
- `docs/integrations/instantpay/go-live-checklist.md`
