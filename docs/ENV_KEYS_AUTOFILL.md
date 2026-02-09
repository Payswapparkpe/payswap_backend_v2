# Env Keys – Jahan zarurat hai wahan autofill

Saari keys jo `.env` mein hain, jahan UI/forms mein zarurat hai wahan **auto pre-fill** ho jati hain.

---

## 1. API Explorer (`/api-explorer/`)

| Field | Source (autofill) |
|--------|-------------------|
| **Authorization / API Key** | `EXPLORER_DEFAULT_API_KEY` (env) → else logged-in user ka **Postman API key** (profile) |
| **Headers tab** (X-Api-Key, Authorization) | Same as above – hamesha isi key se fill hota hai |
| **Postman Sync → Postman API Key** | Same: `EXPLORER_DEFAULT_API_KEY` → else profile `postman_api_key` |

---

## 2. Services → Vendor detail (Euronet / Mobikwik BBPS)

**Test parameters (optional overrides)** form:

- **Euronet:** `base_url`, `merchant_code`, `username`, `password`, `store_code`, `channel_code`, `agent_id`, `salt`, `encryption_key`  
  → Pehle saved `test_params` (service.vendor_config), nahi to **env** se:  
  `EURONET_BBPS_BASE_URL`, `EURONET_BBPS_MERCHANT_CODE`, `EURONET_BBPS_USERNAME`, `EURONET_BBPS_PASSWORD`, etc.

- **Mobikwik:** `base_url`, `client_id`, `client_secret`, `merchant_id`, `api_key`, `secret_key`  
  → Pehle saved `test_params`, nahi to **env** se:  
  `MOBIKWIK_BBPS_BASE_URL`, `MOBIKWIK_BBPS_CLIENT_ID`, `MOBIKWIK_BBPS_CLIENT_SECRET`, `MOBIKWIK_BBPS_MERCHANT_ID`, `MOBIKWIK_BBPS_API_KEY`, `MOBIKWIK_BBPS_SECRET_KEY`

---

## 3. API Vendor List (Postman Sync)

**Postman API Key** input:

- `EXPLORER_DEFAULT_API_KEY` (env) → else user profile ka `postman_api_key`.

---

## 4. Management commands (CLI)

| Command | Key source (autofill) |
|--------|------------------------|
| `python manage.py test_all_api_responses` | `--api-key` → else **EXPLORER_DEFAULT_API_KEY** (env). `--no-env-key` se env key use nahi hogi. |
| `python manage.py test_api_and_check_logs` | `--api-key` → else **EXPLORER_DEFAULT_API_KEY** (env). |

---

## .env mein kya set karein

Jitne bhi keys aap use karte ho, unko `.env` mein set karo; jahan zarurat hai wahan autofill ho jayega:

```bash
# API Explorer + test commands
EXPLORER_DEFAULT_API_KEY=psk_live_...

# Euronet BBPS (Services → BBPS → Euronet test params)
EURONET_BBPS_BASE_URL=https://epayuat.eftapme.com/ENServiceAES256/API
EURONET_BBPS_MERCHANT_CODE=PAY
EURONET_BBPS_USERNAME=PAY_01
EURONET_BBPS_PASSWORD=...
# ... etc.

# Mobikwik BBPS (Services → BBPS → Mobikwik test params)
MOBIKWIK_BBPS_BASE_URL=https://alpha3.mobikwik.com
MOBIKWIK_BBPS_CLIENT_ID=...
MOBIKWIK_BBPS_CLIENT_SECRET=...
MOBIKWIK_BBPS_MERCHANT_ID=...
MOBIKWIK_BBPS_API_KEY=...
MOBIKWIK_BBPS_SECRET_KEY=...
```

Saved test params (service.vendor_config) ko priority milti hai; jab saved value nahi hoti tab env value use hoti hai.
