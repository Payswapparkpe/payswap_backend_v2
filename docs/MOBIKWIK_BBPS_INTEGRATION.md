# Mobikwik BBPS Integration (New API)

## Overview

BBPS (Bharat Bill Payment System) is integrated using **Mobikwik** as the vendor. The integration has been updated to match the **new Mobikwik API** described in the UAT Checklist and Onboarding documents:

- **Token Generation API** – Client ID + Client Secret → access token (used for all subsequent calls).
- **Encrypted request body** – When required: `encryptedSessionKey`, `encryptedPayload`, `keyVersion`, `iv`.
- **APIs**: Token Generation, Balance Check, Validation, View Bill, Recharge, Transaction Status Check.

Partners use API v2 BBPS endpoints to fetch bills, pay bills, and (optionally) check balance.

## Public key (secure API encryption)

Mobikwik provides a zip file (e.g. `mobikwik_public_key_1243428019.zip`) containing:

- `public_key.pem` – RSA public key for encrypting your session key on each request
- `README.txt` – Key version (e.g. 1.0) and instructions

**Setup:**

1. Extract the zip into your project (e.g. into the `Mobikwik/` folder).
2. In `.env`, set:
   - `MOBIKWIK_BBPS_USE_ENCRYPTION=True`
   - `MOBIKWIK_BBPS_PUBLIC_KEY_PATH=Mobikwik/public_key.pem`
   - `MOBIKWIK_BBPS_KEY_VERSION=1.0` (match the version in README.txt)

The integration will then encrypt every API request body (except Token) as: encrypt payload with a random AES key, encrypt that key with Mobikwik’s public key, and send `encryptedSessionKey`, `encryptedPayload`, `keyVersion`, `iv`.

## Configuration

Add to your `.env` (get credentials from Mobikwik BBPS onboarding / API Kit):

```env
MOBIKWIK_BBPS_ENABLED=True
MOBIKWIK_BBPS_CLIENT_ID=your_client_id
MOBIKWIK_BBPS_CLIENT_SECRET=your_client_secret
MOBIKWIK_BBPS_MERCHANT_ID=your_merchant_id
MOBIKWIK_BBPS_API_KEY=your_api_key
MOBIKWIK_BBPS_SECRET_KEY=your_secret_key
MOBIKWIK_BBPS_BASE_URL=https://alpha3.mobikwik.com
MOBIKWIK_BBPS_ENVIRONMENT=UAT
# Optional: enable when Mobikwik requires encrypted request body
MOBIKWIK_BBPS_USE_ENCRYPTION=False
MOBIKWIK_BBPS_PUBLIC_KEY=
MOBIKWIK_BBPS_KEY_VERSION=1
```

- **UAT**: Use Mobikwik’s UAT base URL and credentials from the API Kit.
- **PRODUCTION**: Use production URL and production credentials.
- **Token**: `MOBIKWIK_BBPS_CLIENT_ID` and `MOBIKWIK_BBPS_CLIENT_SECRET` are used for the Token Generation API; the token is then sent in `Authorization: Bearer <token>` for Balance Check, Validation, View Bill, Recharge, and Transaction Status.
- **Encryption**: To encrypt API requests (required for secure integration), extract the public key from the zip Mobikwik provides (`mobikwik_public_key_*.zip`) to e.g. `Mobikwik/public_key.pem`, then set `MOBIKWIK_BBPS_USE_ENCRYPTION=True` and `MOBIKWIK_BBPS_PUBLIC_KEY_PATH=Mobikwik/public_key.pem` (or set `MOBIKWIK_BBPS_PUBLIC_KEY` to the PEM string). Include `keyVersion` (e.g. `1.0`) in each request.

## New API Mapping (Mobikwik UAT)

| UAT API                  | Internal method           | Partner API (API v2)              |
|--------------------------|---------------------------|-----------------------------------|
| Token Generation         | `get_token()`             | (used internally)                |
| Balance Check            | `balance_check()`         | (can be exposed if needed)        |
| Validation               | `validation()`            | Bill fetch                        |
| View Bill                | `view_bill()`             | Bill fetch (fallback)             |
| Recharge                 | `recharge()`              | Bill pay                          |
| Transaction Status Check | `transaction_status()`    | Payment status by ref_id          |

## API Endpoints (API v2)

All require API key authentication and `bbps` service permission.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/bbps/operators/?category=ELECTRICITY` | List operators/billers (optional category) |
| POST | `/api/v2/bbps/bill/fetch/` | Fetch bill details (Validation / View Bill) |
| POST | `/api/v2/bbps/bill/pay/` | Pay bill (Recharge) |
| GET | `/api/v2/bbps/bill/status/<ref_id>/` | Payment status by ref_id (Transaction Status) |

### Bill fetch (POST /api/v2/bbps/bill/fetch/)

```json
{
  "operator_id": "OP001",
  "customer_id": "1234567890",
  "subscriber_id": ""
}
```

### Bill pay (POST /api/v2/bbps/bill/pay/)

```json
{
  "operator_id": "OP001",
  "customer_id": "1234567890",
  "amount": "500.00",
  "ref_id": "UNIQUE_REF_123",
  "subscriber_id": ""
}
```

### API key permissions

For a partner API key, enable BBPS actions:

- `bbps.operators`
- `bbps.fetch_bill`
- `bbps.pay_bill`
- `bbps.payment_status`

## Code Layout

- **Config**: `core/config.py` – `MOBIKWIK_BBPS_*` settings (including Client ID/Secret and encryption).
- **Vendor client**: `portal/services/vendors/mobikwik.py` – `MobikwikBBPSClient` (token, optional encryption, Validation/View Bill/Recharge/Transaction Status).
- **Service layer**: `portal/services/bbps_service.py` – `BBPSService` (used by API views).
- **API v2**: `api/v2/bbps_views.py` – BBPS views; `api/v2/serializers.py` – BBPS serializers; `api/v2/urls.py` – BBPS routes.

## Mobikwik-specific adjustments

Exact **endpoint paths** and **encryption algorithm** may differ per Mobikwik API Kit. Update in `portal/services/vendors/mobikwik.py`:

1. **Paths**: `DEFAULT_PATHS` (token, balance, validation, view_bill, recharge, transaction_status, operators) – replace with paths from your Mobikwik contract.
2. **Encryption**: If they use a different scheme (e.g. AES-CBC instead of AES-GCM, or different key wrap), adjust `_encrypt_payload()`.
3. **Token request**: If Token API expects different body/headers, adjust `get_token()`.
4. **Response**: If responses are encrypted, add decryption in `_request()` or per-method.

## UAT checklist (from Mobikwik docs)

For every API where request body is required, partners must log (for UAT):

- Request body with **both** encrypted and decrypted values: `encryptedSessionKey`, `encryptedPayload`, `keyVersion`, `iv`.
- Complete cURL (including headers), request URL, request body, response for: Token (success/fail), Balance Check (success/fail), Validation (success/fail), View Bill (success/fail), Recharge (success/fail/pending), Transaction Status (success/fail/pending).
- Handling of pending, timeout, retry/status-check interval, and token expiry.

## Token failure troubleshooting

### "nodename nor servname provided, or not known"

This is a **DNS resolution error**: the hostname in `MOBIKWIK_BBPS_BASE_URL` cannot be resolved on your machine or network.

- **Fix:** Use the exact base URL from **Mobikwik RT-Recharge & Bill Payment API Documentation**. For testing use `https://alpha3.mobikwik.com` (set `MOBIKWIK_BBPS_BASE_URL=https://alpha3.mobikwik.com` in `.env`).
- **Check DNS:** Run `nslookup alpha3.mobikwik.com` or `ping alpha3.mobikwik.com`. If it fails, the testing URL is not resolvable from your environment.

### "Expecting value: line 1 column 1 (char 0)" or "non-JSON response"

The token API returned a non-JSON response (e.g. HTML error page or empty body). Usually the **token path** is wrong.

- **Fix:** Token path from the PDF is **`/recharge/v1/verify/retailer`**. Set in `.env`: `MOBIKWIK_BBPS_TOKEN_PATH=/recharge/v1/verify/retailer`
- After the next run, the error message will include **HTTP status** and a **short preview** of the response so you can confirm (e.g. 404 HTML vs 401).

### Other token errors

If you see **"Failed to obtain Mobikwik BBPS token"** with a different message:

1. **Check the actual error** – The message now includes the underlying reason (e.g. connection error, HTTP 401, "Token not found in response"). Look at the log entry’s **Message** or **Additional Data** for the full text.
2. **Confirm Token API from the PDF** – Open **Mobikwik RT-Recharge & Bill Payment API Documentation** and find the exact:
   - **Token / Auth API URL** (base URL + path; testing base: `https://alpha3.mobikwik.com`).
   - **Request format** (JSON body keys: e.g. `clientId`/`clientSecret` or `client_id`/`client_secret`).
3. **Override token path** – If the path is different from `/api/v1/auth/token`, set in `.env`:
   - `MOBIKWIK_BBPS_TOKEN_PATH=/oauth/token` (or the path from the doc).
4. **Override base URL** – For UAT, Mobikwik may give a different host (e.g. `https://uat-api.mobikwik.com`). Set `MOBIKWIK_BBPS_BASE_URL` accordingly.
5. **Credentials** – Ensure `MOBIKWIK_BBPS_CLIENT_ID` and `MOBIKWIK_BBPS_CLIENT_SECRET` match the values from the API Kit (e.g. from the ZIP or onboarding email).

## Testing

### 1. Add credentials to `.env`

```env
MOBIKWIK_BBPS_ENABLED=True
MOBIKWIK_BBPS_CLIENT_ID=your_client_id
MOBIKWIK_BBPS_CLIENT_SECRET=your_client_secret
MOBIKWIK_BBPS_BASE_URL=https://alpha3.mobikwik.com
MOBIKWIK_BBPS_ENVIRONMENT=UAT
```

### 2. Run the Mobikwik BBPS test command

```bash
python manage.py test_mobikwik_bbps
```

This tests Token Generation, Balance Check, and Operators. Use `--skip-balance` or `--skip-operators` to skip those calls. You can also pass credentials on the command line (without storing in `.env`):

```bash
python manage.py test_mobikwik_bbps --client-id "YOUR_CLIENT_ID" --client-secret "YOUR_CLIENT_SECRET"
```

### 3. Test all operators / billers (from Operators.xlsx)

To run **View Bill** for every BBPS operator in your Excel and see which succeed or fail:

```bash
python manage.py test_all_bbps_operators
```

Options:

- `--category ELECTRICITY` – only operators in that category
- `--customer-id "1234567890"` – consumer ID used for View Bill (default: `0`)
- `--limit 20` – test at most 20 operators (default: all)
- `--dry-run` – only list operators from Excel, no API calls
- `--verbose` – print full API response per operator

Example: test first 10 DTH operators with a test customer ID:

```bash
python manage.py test_all_bbps_operators --category DTH --limit 10 --customer-id TEST
```

**Retry failures (fix length validation and retry):**  
Use `--retry-failures` so operators that fail with "Please enter X character long …" are retried once with a length-correct consumer ID:

```bash
python manage.py test_all_bbps_operators --limit 50 --retry-failures --output bbps_operators_test_results.json
```

**Test all operators/billers (1356 in Excel):**  
Run without `--limit` to test every BBPS operator. This takes ~25+ minutes. Run in background and check the output file:

```bash
nohup python3 manage.py test_all_bbps_operators --retry-failures --output bbps_operators_test_results.json > bbps_test.log 2>&1 &
tail -f bbps_test.log
```

### 4. Use API v2 BBPS endpoints

1. Create a partner and API key with BBPS permissions.
2. Call operators, then bill fetch, then bill pay with the same API key.

If BBPS is not configured, all BBPS endpoints return `503 Service Unavailable`.
