# PayPoint DMT API Integration

Official documentation: **[PayPoint DMT API – Overview](https://docs.paypointindia.co.in/api/paypoint-dmt-api/dmt-api/overview)**

## Overview (from PayPoint docs)

- **Technology**: RESTful API with output in `application/json`. **HTTP POST** for all requests.
- **Credentials**: PayPoint provides **UserCode**, **Password**, **IdentificationCode**, and **Key** to each client.
- **Encryption**: **UserCode**, **Password**, and **IdentificationCode** must be **encrypted using the "Encrypt" API call** before being sent in every DMT request (same mechanism as PayPoint AEPS).
- **IP whitelisting**: Client must provide IPs to be whitelisted to access the API.

## Implementation in Payswap

| Config (.env) | Description |
|---------------|-------------|
| `PAYPOINT_DMT_ENABLED` | Set `True` to enable integration |
| `PAYPOINT_DMT_BASE_URL` | API base URL (default: `https://api.paypointindia.co.in`) |
| `PAYPOINT_DMT_USER_CODE` | UserCode from PayPoint |
| `PAYPOINT_DMT_PASSWORD` | Password from PayPoint |
| `PAYPOINT_DMT_IDENTIFICATION_CODE` | IdentificationCode from PayPoint |
| `PAYPOINT_DMT_KEY` | Key from PayPoint (not encrypted) |
| `PAYPOINT_DMT_ENVIRONMENT` | UAT or PRODUCTION |

### Flow

1. **Encrypt API**: Before each DMT request, the client calls the Encrypt API with UserCode, Password, IdentificationCode (and Key). Encrypted values are cached for reuse.
2. **DMT requests**: Register Sender, Add Beneficiary, Remit, Transaction Status, Get Beneficiaries are sent as HTTP POST with the encrypted credentials in the request body.

### Endpoint paths (align with PayPoint contract)

Current implementation uses these paths; update in `portal/services/vendors/paypoint_dmt.py` if PayPoint’s full DMT API doc specifies different paths:

- `POST /api/Encrypt` – get encrypted UserCode, Password, IdentificationCode (internal; before each request)
- `POST /api/RegisterSender` – sender/remitter registration
- `POST /api/AddBeneficiary` – add beneficiary
- `POST /api/Remit` – money transfer
- `POST /api/TransactionStatus` – transaction status (with ReferenceId)
- `POST /api/GetBeneficiaries` – list beneficiaries for a sender

Request/response field names may need to be adjusted to match PayPoint’s exact DMT API specification.

## Partner API (v2)

Partners use API v2 with API key and DMT permissions. Grant the following on the API key:

| Endpoint | Method | Required action |
|----------|--------|-----------------|
| `/api/v2/dmt/register-sender/` | POST | `dmt.register_sender` |
| `/api/v2/dmt/add-beneficiary/` | POST | `dmt.add_beneficiary` |
| `/api/v2/dmt/remit/` | POST | `dmt.remit` |
| `/api/v2/dmt/status/<ref_id>/` | GET | `dmt.transaction_status` |
| `/api/v2/dmt/beneficiaries/` | POST | `dmt.get_beneficiaries` |

Encrypt is not exposed to partners (used internally).

## Portal UI

- **Services → DMT** shows the **PayPoint** vendor card (card name: PayPoint).
- **PayPoint** (DMT) vendor detail page lists all 5 DMT APIs and API v2 endpoint references.

## Postman

The collection **Payswap - All APIs** includes folder **API v2 - DMT (PayPoint)** with requests for Register Sender, Add Beneficiary, Remit, Transaction Status, and Get Beneficiaries. Set `api_key` and ensure the key has `dmt.*` permissions.
