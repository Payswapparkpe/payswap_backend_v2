# Instantpay Endpoint Matrix (Hub Mapping)

This matrix maps business APIs to Hub API v2 endpoints, permission keys, and transaction lifecycle.

| Business API | Hub Endpoint | Service.Action Permission | Transaction Type | Async/Sync |
|---|---|---|---|---|
| AEPS Cash Withdrawal | `POST /api/v2/aeps/withdraw/` | `aeps.withdraw` | `AEPS_WITHDRAW` | Sync |
| AEPS Balance Check | `POST /api/v2/aeps/balance-check/` | `aeps.balance_check` | `AEPS_BALANCE` | Sync |
| AEPS Account Statement | `POST /api/v2/aeps/account-statement/` | `aeps.account_statement` | `AEPS_STATEMENT` | Sync |
| DMT Transfer | `POST /api/v2/dmt/transfer/` | `dmt.transfer` | `DMT_TRANSFER` | Sync |
| Remittance Domestic | `POST /api/v2/dmt/remittance/domestic/` | `dmt.remittance_domestic` | `REMITTANCE_DOMESTIC` | Sync |
| Remittance Nepal | `POST /api/v2/dmt/remittance/nepal/` | `dmt.remittance_nepal` | `REMITTANCE_NEPAL` | Async |
| Credit Card Bill Payment | `POST /api/v2/billpay/credit-card/pay/` | `billpay.credit_card_pay` | `CC_BILLPAY` | Sync |
| RC Verification | `POST /api/v2/vehicle/rc-verify/` | `vehicle.rc_verify` | `VEHICLE_RC_VERIFY` | Sync |
| Vehicle Challan Lookup | `POST /api/v2/vehicle/challan-lookup/` | `vehicle.challan_lookup` | `VEHICLE_CHALLAN` | Sync |
| DigiLocker Init | `POST /api/v2/identity-docs/digilocker/init/` | `identity_docs.digilocker_init` | `DIGILOCKER_INIT` | Async |
| DigiLocker Status | `GET /api/v2/identity-docs/digilocker/status/<reference_id>/` | `identity_docs.digilocker_status` | `DIGILOCKER_STATUS` | Async |
| Card BIN Lookup | `POST /api/v2/cards/bin-lookup/` | `cards.bin_lookup` | `CARD_BIN_LOOKUP` | Sync |
| Credit Report | `POST /api/v2/credit/report/` | `credit.report` | `CREDIT_REPORT` | Async |
| Credit Score Simulator | `POST /api/v2/credit/score-simulator/` | `credit.score_simulator` | `CREDIT_SCORE_SIM` | Sync |
| Merchant Onboarding | `POST /api/v2/merchant/onboarding/` | `merchant.onboarding` | `MERCHANT_ONBOARD` | Async |
| Transaction Status | `GET /api/v2/reconciliation/transaction-status/<partner_txn_id>/` | `reconciliation.transaction_status` | `TXN_STATUS` | Sync |

## Lifecycle States

Standardized statuses in Hub transaction store:

- `initiated`
- `pending`
- `success`
- `failed`
- `reversed`

## Notes

- For async APIs, status polling endpoint is mandatory.
- All transactional POST endpoints require `idempotency_key` header.
- `partner_txn_id` is unique per partner for reconciliation.
