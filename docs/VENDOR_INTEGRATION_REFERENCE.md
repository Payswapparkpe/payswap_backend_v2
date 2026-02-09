# Vendor Integration Reference (Euronet BBPS, Cashfree, Mobikwik, PayPoint AEPS/DMT)

This document explains how each vendor integration works, which **project assets** to use for correct understanding, **required parameters**, **env keys**, and **how tests work**. Use it together with the folders **Euronet BBPS**, **Cashfree**, **Mobikwik**, and **payswap old** (PayPoint AEPS context) and online API docs where noted.

---

## 1. Euronet BBPS (Bharat Connect / EFT APME)

**Source for correct understanding:** `Euronet BBPS/` folder  
- **Euronet_BBPS_Postman_Collection.json** – Single EnService endpoint; all request bodies and variables.  
- **UAT details.rtf** – UAT credentials and parameters.

**How it works:**  
- Single endpoint: `POST {{baseUrl}}/EnService` (base URL = `https://epayuat.eftapme.com/ENServiceAES256/API` for UAT).  
- Every request has: `serviceType`, `merchantCode`, `username`, `password`, `storeCode`, `channelCode`, `agentId`, `salt`. Optionally `encryptionKey` if required by API.  
- Operation-specific: **Balance** – `BALANCE_ENQUIRY`; **Get Billers** – `GET_BILLERS`; **Fetch Bill** – `FETCH_BILL` + `billerId`, `consumerId`; **Pay Bill** – `PAY_BILL` + `billerId`, `consumerId`, `amount`, `refId`; **Status** – `TRANSACTION_STATUS` + `refId`.

**Required .env keys (all from .env, no hardcoding):**

```env
EURONET_BBPS_ENABLED=True
EURONET_BBPS_BASE_URL=https://epayuat.eftapme.com/ENServiceAES256/API
EURONET_BBPS_MERCHANT_CODE=PAY
EURONET_BBPS_USERNAME=PAY_01
EURONET_BBPS_PASSWORD=PAY_01
EURONET_BBPS_STORE_CODE=PAY_01
EURONET_BBPS_CHANNEL_CODE=INT
EURONET_BBPS_AGENT_ID=EU01EU02000000000001
EURONET_BBPS_SALT=Os3dcl82
EURONET_BBPS_ENCRYPTION_KEY=abcd12345678901*
```

**Code:** `portal/services/vendors/euronet.py` – uses only `core.config` EURONET_BBPS_*.

**Tests / check system:**  
- **Postman:** Import `Euronet BBPS/Euronet_BBPS_Postman_Collection.json`, set variables, run 1→5 in order.  
- **Portal:** Services → BBPS → Euronet card → **Test parameters** (optional overrides: base URL, merchant code, username, password, store code, channel code, agent ID, salt, encryption key). **Save** to store in `service.vendor_config`; all tab tests and **Test all APIs** use these values when set. **Test all APIs** runs Balance Enquiry + Get Billers and shows combined results.  
- **CLI:** `python manage.py test_euronet_bbps` (validates config + Balance + Get Billers).

**Docs:** `docs/EURONET_BBPS_INTEGRATION.md`.

---

## 2. Cashfree (Verification & Payment Gateway)

**Source for correct understanding:** `Cashfree/` folder  
- **public-key.zip** – Public key for signature (if required when IP is not whitelisted).

**How it works:**  
- **Verification (KYC):** PAN, Aadhaar, Bank, DL, Voter ID, Passport, GST, Face Match, Face Liveness.  
  - Client: `portal/services/vendors/cashfree.py` – uses `CASHFREE_API_KEY`, `CASHFREE_API_SECRET`, optional `CASHFREE_PUBLIC_KEY` / `CASHFREE_PUBLIC_KEY_PATH`.  
- **Payment Gateway (PG):** Initiate, status, refund.  
  - Client: `portal/services/vendors/cashfree_pg.py` – uses `CASHFREE_PG_*` from .env.

**Required .env keys:**

```env
# Cashfree Verification (KYC)
CASHFREE_API_KEY=your-api-key
CASHFREE_API_SECRET=your-api-secret
CASHFREE_BASE_URL=https://api.cashfree.com
# Optional: if IP not whitelisted
CASHFREE_PUBLIC_KEY_PATH=Cashfree/public_key.pem

# Cashfree Payment Gateway
CASHFREE_PG_CLIENT_ID=
CASHFREE_PG_CLIENT_SECRET=
CASHFREE_PG_PARTNER_KEY=
CASHFREE_PG_CLIENT_SIGNATURE=
CASHFREE_PG_PARTNER_MERCHANT_ID=
CASHFREE_PG_ENVIRONMENT=SANDBOX
```

**Tests / check system:**  
- **Portal:** Services → Cashfree / Cashfree PG cards → Test panels.  
- **CLI:** `python manage.py test_all_cashfree_apis` – runs verification APIs and logs results.

**Docs:** `docs/CASHFREE_API_TEST_RESULTS.md`, `docs/CASHFREE_SIGNATURE_SETUP.md`.

---

## 3. Mobikwik BBPS

**Source for correct understanding:** `Mobikwik/` folder  
- **mobikwik_public_key_*.zip** – Contains `public_key.pem` and **README.txt** (key version, encrypt session key with RSA, send encrypted payload + encrypted session key + keyVersion).  
- UAT/Onboarding docx – Token + encrypted request flow.

**How it works:**  
- **Auth:** Token API (Client ID + Client Secret) → access token; token used in `Authorization: Bearer <token>` for all other calls.  
- **Encryption (when required):** Generate AES session key → encrypt payload with AES → encrypt AES key with Mobikwik public key → send `encryptedSessionKey`, `encryptedPayload`, `keyVersion`, `iv`.  
- **APIs:** Token, Balance Check, Validation (bill fetch), View Bill, Recharge (pay), Transaction Status.

**Required .env keys:**

```env
MOBIKWIK_BBPS_ENABLED=True
MOBIKWIK_BBPS_CLIENT_ID=your_client_id
MOBIKWIK_BBPS_CLIENT_SECRET=your_client_secret
MOBIKWIK_BBPS_MERCHANT_ID=your_merchant_id
MOBIKWIK_BBPS_API_KEY=your_api_key
MOBIKWIK_BBPS_SECRET_KEY=your_secret_key
MOBIKWIK_BBPS_BASE_URL=https://alpha3.mobikwik.com
MOBIKWIK_BBPS_ENVIRONMENT=UAT
MOBIKWIK_BBPS_USE_ENCRYPTION=False
MOBIKWIK_BBPS_PUBLIC_KEY_PATH=Mobikwik/public_key.pem
MOBIKWIK_BBPS_KEY_VERSION=1.0
```

**Code:** `portal/services/vendors/mobikwik.py` – Token, balance, validation, view_bill, recharge, transaction_status; encryption when `MOBIKWIK_BBPS_USE_ENCRYPTION=True`.

**Tests / check system:**  
- **Portal:** Services → BBPS → Mobikwik card → **Test parameters** (optional overrides: base URL, client ID, client secret, merchant ID, API key, secret key). **Save** to store in `service.vendor_config`; all tab tests and **Test all APIs** use these values when set. **Test all APIs** runs Token Generation, Balance Check, Get Operators and shows combined results.  
- **CLI:** `python manage.py test_mobikwik_bbps` – Token, Balance, Operators (optional `--client-id`, `--client-secret`).  
- **CLI:** `python manage.py test_all_bbps_operators` – Tests operators from Operators.xlsx via View Bill.

**Docs:** `docs/MOBIKWIK_BBPS_INTEGRATION.md`.

---

## 4. PayPoint AEPS (Aadhaar Enabled Payment System)

**Source for correct understanding:**  
- **Online API docs:** https://docs.paypointindia.co.in/api/paypoint-aeps-api/paypoint/overview  
- **payswap old** – Legacy project context (AEPS/DMT mentioned in meta/keywords); actual integration and **required parameters** follow **PayPoint’s online docs** and env.

**How it works:**  
- **Credentials:** UserCode, Password, IdentificationCode, Key (from PayPoint).  
- **Encrypt API:** Before every AEPS request, call **Encrypt API** with UserCode, Password, IdentificationCode, Key; use returned encrypted values in request body. Key is sent as-is (not encrypted).  
- **IP whitelisting:** Client IPs must be whitelisted by PayPoint.  
- **Endpoints (from PayPoint docs):** Encrypt, BalanceEnquiry, CashWithdrawal, MiniStatement, TransactionStatus, AgentRegistration, etc.

**Required .env keys (all from .env):**

```env
PAYPOINT_AEPS_ENABLED=True
PAYPOINT_AEPS_BASE_URL=https://api.paypointindia.co.in
PAYPOINT_AEPS_USER_CODE=your_usercode
PAYPOINT_AEPS_PASSWORD=your_password
PAYPOINT_AEPS_IDENTIFICATION_CODE=your_identification_code
PAYPOINT_AEPS_KEY=your_key
PAYPOINT_AEPS_ENVIRONMENT=UAT
```

**Code:** `portal/services/vendors/paypoint.py` – Encrypt API, then Balance Enquiry, Cash Withdrawal, Mini Statement, Transaction Status; all params aligned with PayPoint docs (AadhaarNumber, MobileNumber, BankIIN, RdRequest, Latitude, Longitude, TransactionType, Amount, etc.).

**Tests / check system:**  
- **Portal:** Services → AEPS (PayPoint) → Test panel (when vendor is assigned).  
- **CLI:** `python manage.py test_paypoint_aeps` – Validates config, Encrypt API, and (optionally) Balance Enquiry with test data.

**Docs:** `docs/PAYPOINT_AEPS_API.md`.

---

## 5. PayPoint DMT (Domestic Money Transfer)

**Online API docs:** https://docs.paypointindia.co.in/api/paypoint-dmt-api/dmt-api/overview  

Same credential and Encrypt flow as AEPS; different endpoints (RegisterSender, AddBeneficiary, Remit, TransactionStatus, GetBeneficiaries). All keys in .env: `PAYPOINT_DMT_*`.  
**Code:** `portal/services/vendors/paypoint_dmt.py`.  
**Docs:** `docs/PAYPOINT_DMT_API.md`.

---

## Summary: Use of project assets and env

| Vendor        | Project assets for understanding      | Required params / flow           | Keys in .env        | Test commands                          |
|---------------|----------------------------------------|----------------------------------|---------------------|----------------------------------------|
| Euronet BBPS  | `Euronet BBPS/` (Postman + UAT.rtf)   | serviceType + common fields      | EURONET_BBPS_*      | test_euronet_bbps, Portal test panel  |
| Cashfree      | `Cashfree/` (public-key.zip)          | API key/secret, optional PK      | CASHFREE_*, CASHFREE_PG_* | test_all_cashfree_apis, Portal   |
| Mobikwik BBPS | `Mobikwik/` (zip + README.txt)        | Token + encrypted payload        | MOBIKWIK_BBPS_*     | test_mobikwik_bbps, test_all_bbps_operators |
| PayPoint AEPS | Online docs + payswap old (context)    | Encrypt then AEPS; IP whitelist  | PAYPOINT_AEPS_*     | test_paypoint_aeps, Portal             |
| PayPoint DMT  | Online docs                            | Encrypt then DMT endpoints       | PAYPOINT_DMT_*      | Portal                                 |

All integrations use **env files for keys**; no credentials are hardcoded. The existing test and check system (Portal test panels + management commands) validate that each integration works correctly when env is set.

---

## Save / Edit test parameters (Services page)

On **Services → [Service] → [Vendor]** (e.g. BBPS → Euronet or BBPS → Mobikwik):

- **Test parameters** – Optional overrides for that vendor (base URL, credentials, etc.). Fields match the required parameters for that API. Leave blank to use .env.
- **Save test parameters** – Stores values in `service.vendor_config[vendor_code]['test_params']`. All API tests (tabs and **Test all APIs**) then use these overrides when present.
- **Test all APIs** – Runs the main APIs for that vendor in sequence (e.g. Euronet: Balance Enquiry + Get Billers; Mobikwik: Token + Balance + Get Operators) and shows a combined result. Uses saved test params or .env.

This lets the team change test values (e.g. UAT credentials or base URL) without editing .env, and run a full check with one click.
