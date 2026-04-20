# Instantpay Auth, Signing, and Encryption

This guide defines the minimum security contract for Hub to Instantpay calls.

## Authentication Headers

Hub client sends:

- client id (`INSTANTPAY_CLIENT_ID`)
- client secret (`INSTANTPAY_CLIENT_SECRET`)
- timestamp and request id
- content type `application/json`

Exact header names are controlled from one place in the Instantpay client to avoid drift across modules.

## Payload Encryption

- Sensitive fields should be encrypted when required by Instantpay endpoint policy.
- `INSTANTPAY_ENCRYPTION_KEY` is loaded from env.
- Encryption/decryption is implemented in utility methods in the Instantpay client.
- If endpoint does not require encryption, plain JSON payload is used.

## Signing Strategy

- Signature input should include deterministic request fields (timestamp, request id, body digest).
- Signature generation should be centralized in client helper methods.
- Signature validation errors are surfaced as `vendor_auth_failed`.

## Request Correlation

Every outbound request must include:

- `request_id` (Hub generated)
- `partner_reference` where available
- `idempotency_key` for transactional creates

These values are persisted in `InstantpayTransaction` for reconciliation and support.

## Error Normalization

Instantpay error structures may vary by module; Hub normalizes to:

- `error_code`
- `error_message`
- `status`
- `vendor_http_status`
- `retryable` (boolean)

## Environment Separation

- Sandbox and production URLs are selected using `INSTANTPAY_ENVIRONMENT`.
- Production credentials never used in local tests.
- Postman env files contain placeholders only.
