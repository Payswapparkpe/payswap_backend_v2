# Euronet BBPS Integration (Bharat Connect / EFT APME)

## Overview

Euronet BBPS is a **separate BBPS vendor** (no shared config or code with Mobikwik). Single endpoint: **EnService** (AES256 in path). All credentials and config use **EURONET_BBPS_*** only.

**Source:** `Euronet BBPS/UAT details.rtf` – UAT credentials only; request/response schema from Euronet API spec.

---

## UAT Details (from UAT details.rtf – exact values)

| Parameter       | Value |
|----------------|--------|
| **UAT URL**    | `https://epayuat.eftapme.com/ENServiceAES256/API/EnService` |
| **Merchant Code** | `PAY` |
| **Username**   | `PAY_01` |
| **User Pass** | `PAY_01` |
| **Store Code** | `PAY_01` |
| **Channel Code** | `Internet Banking (INT)` |
| **Agent id**   | `EU01EU02000000000001` |
| **Salt Value** | `Os3dcl82` |
| **Encryption key** | `abcd12345678901*` (per UAT details.rtf; store in `.env` as `EURONET_BBPS_ENCRYPTION_KEY`) |

**Note:** If EnService expects channel as code only, use `EURONET_BBPS_CHANNEL_CODE=INT` in `.env`. If it expects full text, use `Internet Banking (INT)` (quote in .env if needed).

---

## UAT verification checklist

- [ ] **URL:** Base URL = `https://epayuat.eftapme.com/ENServiceAES256/API` (no trailing slash); full endpoint = `.../EnService`.
- [ ] **Credentials:** Only `EURONET_BBPS_*` in `.env`; no Mobikwik vars used for Euronet.
- [ ] **Code:** `portal/services/vendors/euronet.py` – no Mobikwik imports or config; only `core.config` EURONET_BBPS_*.
- [ ] **Portal:** BBPS → Euronet card uses Euronet client only; test panel sends `vendor=euronet` to BBPS test APIs.

---

## Testing

### 1. .env check (Euronet only)

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

Do **not** use any Mobikwik variable for Euronet.

### 2. Postman (Euronet UAT)

1. Import **`Euronet BBPS/Euronet_BBPS_Postman_Collection.json`**.
2. Set collection variables from the UAT table above: `baseUrl`, `merchantCode`, `username`, `password`, `storeCode`, `channelCode` (`INT` or `Internet Banking (INT)` as per API), `agentId`, `salt`, `encryptionKey`.
3. Run in order:
   - **1. Balance Enquiry** – POST EnService, body with `serviceType: BALANCE_ENQUIRY` + UAT credentials.
   - **2. Get Billers / Operators** – `serviceType: GET_BILLERS`.
   - **3. Fetch Bill** – `serviceType: FETCH_BILL`, set `billerId`, `consumerId` from billers list / test data.
   - **4. Pay Bill** – `serviceType: PAY_BILL`, set `billerId`, `consumerId`, `amount`, `refId`.
   - **5. Transaction Status** – `serviceType: TRANSACTION_STATUS`, set `refId` from step 4.
4. Confirm success/error format from Euronet; if field names or codes differ from the collection, update the collection and then `portal/services/vendors/euronet.py` to match.

### 3. Portal Admin – Postman in Admin (recommended)

All 5 Postman APIs are available in the portal so you can test from admin instead of Postman.

1. Login as **admin/super**.
2. Go to **Services** → **BBPS** → click **Euronet** card (not Mobikwik).
3. You will see **Euronet BBPS Test Panel (Postman in Admin)** with 6 tabs:
   - **1. Balance Enquiry** – same as Postman #1 (BALANCE_ENQUIRY). Click “Balance Enquiry”, see response.
   - **2. Get Billers** – same as Postman #2 (GET_BILLERS). Optional category, click “Get Billers”, see response.
   - **Operators (Excel)** – load operators from Operators.xlsx (billerId = operator_id).
   - **3. Fetch Bill** – Fetch Bill API. Select operator, consumer ID, click Fetch Bill.
   - **4. Pay Bill** – Pay Bill API. Select operator, consumer ID, amount, Ref ID, click Pay Bill. Note `ref_id`.
   - **5. Payment Status** – Transaction Status API. Enter `ref_id`, click Check Status.

Run in order 1 → 2 → 3 → 4 → 5 to mirror the Postman collection. All calls use **Euronet only** (`vendor=euronet`).

### 4. Logs

- Euronet test panel calls are logged with category **`euronet_bbps`** (Mobikwik uses `mobikwik_bbps`).
- In Logs, filter by `euronet_bbps` to verify only Euronet UAT requests.

---

## Postman Collection

1. Import **`Euronet BBPS/Euronet_BBPS_Postman_Collection.json`** into Postman.
2. Set the **collection variables** (or environment) from the table above.
3. Use the requests under the collection to call:
   - Balance Enquiry  
   - Get Billers / Operators  
   - Fetch Bill  
   - Pay Bill  
   - Transaction Status  
4. Adjust request body/headers as per Euronet’s API spec once you have it. The collection uses the single EnService URL and placeholder bodies so you can test and fix until all responses are correct.
5. After all APIs respond correctly in Postman, the same structure can be implemented in the Euronet client in code.

## Configuration (.env)

```env
# Euronet BBPS (Bharat Connect)
EURONET_BBPS_ENABLED=False
EURONET_BBPS_BASE_URL=https://epayuat.eftapme.com/ENServiceAES256/API
EURONET_BBPS_MERCHANT_CODE=PAY
EURONET_BBPS_USERNAME=PAY_01
EURONET_BBPS_PASSWORD=PAY_01
EURONET_BBPS_STORE_CODE=PAY_01
EURONET_BBPS_CHANNEL_CODE=INT
EURONET_BBPS_AGENT_ID=EU01EU02000000000001
EURONET_BBPS_SALT=Os3dcl82
EURONET_BBPS_ENCRYPTION_KEY=your_encryption_key_from_euronet
```

## BBPS Service – Vendor Selection

- In **Portal → Services → BBPS** you will see two cards: **Mobikwik** and **Euronet**.
- Default remains **Mobikwik**. When Euronet is configured and chosen (or set as default in config), the BBPS service uses the Euronet client for operators, fetch bill, pay bill, and status.

## API v2 – Euronet integration

Partner API (API key auth) ab **vendor** support karta hai. Euronet use karne ke liye `vendor=euronet` bhejein:

- **GET** `/api/v2/bbps/operators/?category=ELECTRICITY&vendor=euronet` – operators/billers (Euronet)
- **POST** `/api/v2/bbps/bill/fetch/` – body: `operator_id`, `customer_id`, `vendor`: `"euronet"`, optional: `subscriber_id`, `ad1`–`ad9`
- **POST** `/api/v2/bbps/bill/pay/` – body: `operator_id`, `customer_id`, `amount`, `ref_id`, `vendor`: `"euronet"`, optional: `subscriber_id`, `ad1`–`ad9`
- **GET** `/api/v2/bbps/bill/status/<ref_id>/?vendor=euronet` – payment status (Euronet)

`vendor` na bhejne par default **mobikwik** use hota hai.

## Code Layout

- **Config**: `core/config.py` – `EURONET_BBPS_*` settings.
- **Vendor client**: `portal/services/vendors/euronet.py` – Euronet BBPS client (same interface as Mobikwik: operators, fetch_bill, pay_bill, pay_status, balance_check).
- **BBPS service**: `portal/services/bbps_service.py` – supports both Mobikwik and Euronet; selects vendor by request param.
- **API v2**: `api/v2/bbps_views.py` – all BBPS endpoints accept `vendor` (query or body); Euronet fully integrated.
- **Portal**: BBPS service detail shows both vendor cards; Euronet has its own test panel (Postman in Admin).

## API Spec Required

The exact **request/response schema** (field names, service codes, hash algorithm) for EnService is not in the repo. You need to:

1. Get the API specification (PDF/Word) from Euronet for EnService (single endpoint).
2. Test each operation in Postman until responses are correct.
3. Align `portal/services/vendors/euronet.py` with the same request/response format and then run end-to-end tests from the portal.

## Files in Euronet BBPS Folder

- **UAT details.rtf** – UAT URL and credentials (used for this doc and Postman).
- **Bharat-Connect-MediaKit.zip** – Brand assets (logos, guidelines); no API spec.
- **Mobile screen.docx** / **Screen for Agent, Internet channel.docx** – UI references; check for any API or field hints.
