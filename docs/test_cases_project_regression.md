# Project Regression Test Cases

This checklist is designed for repeated QA runs across core Payswap + ParkPe flows.

## 1) Authentication

- Login with valid mobile + OTP returns dashboard.
- Login with invalid OTP shows error and does not issue token.
- Login lockout after max failed OTP attempts.
- Token refresh works and protected APIs stay accessible.
- Logout clears session and protected routes redirect to login.

## 2) ParkPe Connect

- Vehicle list loads for authenticated user.
- Vehicle detail page shows QR sticker and RC cards.
- Vehicle detail page has no nested inner scroll traps on desktop.
- Copy registration number action works and feedback toast appears.
- Delete vehicle OTP flow rejects invalid OTP and accepts valid OTP.

## 3) BBPS Bill Fetch + Pay

- Category list API returns 200 with non-empty categories.
- Operator list API returns electricity billers including CESU Odisha.
- Bill fetch with valid consumer id returns amount + due data.
- Bill fetch with invalid consumer id returns clear non-500 error.
- Voucher pay with valid voucher/pin returns success or submitted state.
- Voucher pay with wrong pin returns 400 with meaningful error.
- Voucher pay with insufficient balance returns 402.
- BBPS vendor pending status is shown as pending/not-confirmed in UI.

## 4) Voucher

- Voucher list API returns user-scoped vouchers only.
- Voucher details API masks sensitive fields unless explicitly requested.
- Reveal PIN requires auth and proper voucher ownership.
- Voucher debit creates ledger entry with correct amount and reference.
- Rollback credit creates compensating ledger entry with trace metadata.

## 5) Payments + Status

- Payment status page shows success only for confirmed success.
- Pending/unknown gateway status is not shown as final success.
- Payment receipt route renders transaction metadata safely.
- Payment history list includes latest transaction with correct status.

## 6) Wallet + Accounting

- Wallet debit cannot drive balance negative.
- Idempotent transaction reference does not double-debit.
- Partner accounting creates revenue entries once per reference id.

## 7) API Contract + Error Format

- Standard response includes request_id/response_id for API errors.
- Internal server errors never leak stack traces to client responses.
- Validation failures return consistent 4xx payload format.

## 8) Security + Access Control

- Unauthenticated request to protected route returns 401/403.
- Cross-user access to voucher/connect resources is blocked.
- Role-gated admin endpoints reject customer users.

## 9) Observability

- Key flows write structured logs with request correlation IDs.
- BBPS fetch/pay failures log operator and reference context.
- Rollback failures emit warning/error logs for reconciliation.

## 10) Smoke API Set (must pass each release)

- `GET /api/v1/runtime-config/?app=parkpe`
- `POST /api/auth/login`
- `GET /api/auth/profile`
- `GET /api/connect/vehicles/`
- `GET /api/bbps/categories`
- `GET /api/bbps/operators?category=electricity`
- `POST /api/bbps/fetch-bill`
- `POST /api/bbps/pay`
- `GET /api/voucher/vouchers`

