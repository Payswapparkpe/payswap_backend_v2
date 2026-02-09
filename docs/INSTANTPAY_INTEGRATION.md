# Instantpay API Integration

Integration with [Instantpay Developer API](https://developers.instantpay.in/) – Identity, Banking, Payouts, AePS, Collect, Tax, AI/ML, and more.

## Configuration

Set in `.env` (already added from your keys):

- `INSTANTPAY_CLIENT_ID` – Client Id
- `INSTANTPAY_CLIENT_SECRET` – Client Secret  
- `INSTANTPAY_ENCRYPTION_KEY` – Encryption Key (for AES-256-CBC on sensitive fields)
- `INSTANTPAY_ENVIRONMENT` – `SANDBOX` or `PRODUCTION`
- `INSTANTPAY_BASE_URL` – (optional) Override base URL; defaults by environment

## Portal

1. **Services** → **Instantpay** card → **Instantpay** vendor.
2. **Instantpay vendor detail** shows:
   - Quick Test: GSTIN Verification, PIN Code Lookup (form POST to test endpoint).
   - APIs by Category: Asset Verifications, Banking, Business Verifications, Tax Data, Financial Verifications, Location, Mobile Based, Digital KYC, Payouts, Other, AI/Utility, Cards & Vouchers, Financial Inclusion.

## Test API (portal)

- **POST** `/services/<service_id>/instantpay-test-api/`
- Body (form or JSON): `api_code` + params:
  - `api_code=gstin` + `gstin=<15-char GSTIN>`
  - `api_code=pin_code_lookup` + `pincode=<6-digit>`
- Returns JSON: `success`, `status_code`, `response`, `error`.

## Client (Python)

```python
from portal.services.vendors.instantpay import InstantpayClient, INSTANTPAY_API_CATEGORIES

client = InstantpayClient()
if client.is_configured():
    # Tax
    r = client.gstin_verification("27AABCU9603R1ZM", client_ip=request_ip)
    # Location
    r = client.pin_code_lookup("110001", client_ip=request_ip)
    # Banking
    r = client.balance_check({"account_id": "..."}, client_ip=request_ip)
    # Payouts
    r = client.payouts_bank_list(client_ip=request_ip)
    # etc.
```

## API Categories (all integrated in client)

| Category | APIs |
|----------|------|
| Asset Verifications | EPFO UAN, Driving License, Vehicle Challan |
| Banking | Balance Check, Account Statement |
| Business Verifications | LEI, FSSAI, TAN Plus |
| Tax Data | GSTIN, GSTIN Plus, Aadhaar-PAN Linking |
| Financial Verifications | PEP & Sanctions, Verify UPI VPA, Bank Account |
| Location | IP Lookup, PIN Code Lookup |
| Mobile Based | Mobile to Address, Mobile to UPI VPA, Mobile to Name |
| Digital KYC | Profile Enrichment, Face Liveness, Digilocker |
| Payouts | Bank List, Bank Accounts, Create Payout |
| Other | Transaction Status, Merchant Onboarding |
| AI/Utility | Image Moderation, Face Detection, Face Comparison |
| Cards & Vouchers | Corporate Gift Cards, Brand Voucher |
| Financial Inclusion | AePS, Remittance Domestic, Remittance Nepal |

Authentication uses headers: `X-Ipay-Auth-Code: -1`, `X-Ipay-Client-Id`, `X-Ipay-Client-Secret`, `X-Ipay-Endpoint-Ip` (client IP). Sensitive fields (e.g. Aadhaar) use AES-256-CBC with `INSTANTPAY_ENCRYPTION_KEY`.
