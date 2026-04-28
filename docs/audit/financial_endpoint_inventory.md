# Financial Endpoint Inventory (Security Remediation)

This inventory classifies billable or money-impacting endpoints to drive idempotency, ordering, and concurrency hardening.

## API v2 Endpoints

### Local DB + Partner Wallet Mutation
- `POST /api/v2/vouchers/issue/` in `backend/api/v2/voucher_views.py`
  - Creates voucher via `VoucherService.issue_single_voucher()`
  - Charges partner via `PartnerAccountingService.charge_partner_for_service()`
- `POST /api/v2/vouchers/redeem/pin/verify/` in `backend/api/v2/voucher_views.py`
  - Redeems voucher in DB
  - Records partner revenue path (`record_transaction`) and hub income
- `POST /api/v2/vouchers/redeem/otp/verify/` in `backend/api/v2/voucher_views.py`
  - Final redeem path with voucher state transitions

### External Vendor-Backed (May Be Billable)
- KYC verification endpoints in `backend/api/v2/kyc_views.py`
  - `POST /api/v2/kyc/pan/verify/`
  - `POST /api/v2/kyc/aadhaar/verify/`
  - `POST /api/v2/kyc/bank/verify/`
  - `POST /api/v2/kyc/driving-license/verify/`
  - `POST /api/v2/kyc/voter-id/verify/`
  - `POST /api/v2/kyc/passport/verify/`
  - `POST /api/v2/kyc/gst/verify/`
  - `POST /api/v2/kyc/face-match/`
  - `POST /api/v2/kyc/face-liveness/`
- BBPS endpoints in `backend/api/v2/bbps_views.py`
  - `POST /api/v2/bbps/bill/fetch/` (vendor fetch flow; often billable by providers)
  - `POST /api/v2/bbps/bill/pay/` (money movement)
- Instantpay endpoints in `backend/api/v2/instantpay_views.py`
  - Includes AEPS, DMT, remittance, credit card bill pay, merchant onboarding, and other transactional vendor calls.
- Payment gateway endpoints in `backend/api/v2/payment_views.py`
  - `POST /api/v2/payments/initiate/`
  - `POST /api/v2/payments/{payment_id}/refund/`

### Async/Task-Backed Or Side-Effect Auxiliary
- Hub income/cost tracking from request handlers:
  - `portal.services.hub_income_service.record_hub_income()`
- Vendor status lookup or reconciliation:
  - `GET /api/v2/bbps/bill/status/{ref_id}/`
  - `GET /api/v2/instantpay/transactions/{partner_txn_id}/status/`

## Security Controls Mapping
- **Mandatory idempotency**: all state-changing POST endpoints above.
- **Strict reference IDs**: all partner wallet debit/credit and provider transaction records.
- **Ordering guarantees**: avoid success paths where external or local side effects occur before balance authorization/debit.
- **Rate controls**: API-key + service + partner dimensions on all high-risk endpoints.
