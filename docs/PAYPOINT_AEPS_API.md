# PayPoint AEPS API Integration

Official documentation: **[PayPoint AEPS API – Overview](https://docs.paypointindia.co.in/api/paypoint-aeps-api/paypoint/overview)**

## Overview (from PayPoint docs)

- **Technology**: RESTful API with output in `application/json`. **HTTP POST** for all requests.
- **Credentials**: PayPoint provides **UserCode**, **Password**, **IdentificationCode**, and **Key** to each client.
- **Encryption**: **UserCode**, **Password**, and **IdentificationCode** must be **encrypted using the "Encrypt" API call** before being sent in every AEPS request.
- **IP whitelisting**: Client must provide IPs to be whitelisted to access the API.

## Implementation in Payswap

| Config (.env) | Description |
|---------------|-------------|
| `PAYPOINT_AEPS_ENABLED` | Set `True` to enable integration |
| `PAYPOINT_AEPS_BASE_URL` | API base URL (default: `https://api.paypointindia.co.in`) |
| `PAYPOINT_AEPS_USER_CODE` | UserCode from PayPoint |
| `PAYPOINT_AEPS_PASSWORD` | Password from PayPoint |
| `PAYPOINT_AEPS_IDENTIFICATION_CODE` | IdentificationCode from PayPoint |
| `PAYPOINT_AEPS_KEY` | Key from PayPoint (not encrypted) |
| `PAYPOINT_AEPS_ENVIRONMENT` | UAT or PRODUCTION |

### Flow

1. **Encrypt API**: Before each AEPS request, the client calls the Encrypt API with UserCode, Password, IdentificationCode (and Key). Encrypted values are cached for reuse.
2. **AEPS requests**: Balance Enquiry, Cash Withdrawal, Mini Statement, and Transaction Status are sent as HTTP POST with the encrypted credentials in the request body.

### Endpoint paths (align with PayPoint contract)

Current implementation uses these paths; update in `portal/services/vendors/paypoint.py` if PayPoint’s full API doc specifies different paths:

- `POST /api/Encrypt` – get encrypted UserCode, Password, IdentificationCode (internal; before each request)
- `POST /api/BalanceEnquiry` – balance enquiry
- `POST /api/CashWithdrawal` – cash withdrawal
- `POST /api/MiniStatement` – mini statement
- `POST /api/TransactionStatus` – transaction status (with ReferenceId)
- `POST /api/TransactionCheckStatus` – transaction check status (alias; change path if PayPoint uses only TransactionStatus)
- `POST /api/AgentRegistration` – agent registration
- `POST /api/UpdateAgentDetails` – update agent details
- `POST /api/AgentServiceStatus` – check agent service status
- `POST /api/AgentAuthentication` – check agent authentication
- `POST /api/TwoFactorAuthentication` – two factor authentication

Request/response field names may need to be adjusted to match PayPoint’s exact API specification.

## Partner API (v2)

Partners use API v2 with API key and AEPS permissions:

| Endpoint | Method | Required action |
|----------|--------|-----------------|
| `/api/v2/aeps/balance/` | POST | `aeps.balance_enquiry` |
| `/api/v2/aeps/withdrawal/` | POST | `aeps.cash_withdrawal` |
| `/api/v2/aeps/mini-statement/` | POST | `aeps.mini_statement` |
| `/api/v2/aeps/status/<ref_id>/` | GET | `aeps.transaction_status` |
| `/api/v2/aeps/agent-registration/` | POST | `aeps.agent_registration` |
| `/api/v2/aeps/update-agent-details/` | POST | `aeps.update_agent_details` |
| `/api/v2/aeps/agent-service-status/` | POST | `aeps.agent_service_status` |
| `/api/v2/aeps/agent-authentication/` | POST | `aeps.agent_authentication` |
| `/api/v2/aeps/two-factor-auth/` | POST | `aeps.two_factor_authentication` |

Encrypt is not exposed to partners (used internally). Grant the above permissions on the API key as needed.
