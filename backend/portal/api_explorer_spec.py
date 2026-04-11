"""
API Explorer (Postman-style) spec: internal system APIs (v1) and vendor testing endpoints.
Paths are from site root e.g. /api/v1/health/, /api/v1/vouchers/issue/.
Each endpoint can have headers and params (required/default values) for the Explorer UI.
Vendor categorization for API Explorer card layout.
"""
import re

# Vendor categories for API Explorer – group vendors by type
VENDOR_CATEGORIES = {
    'payment': {'name': 'Payment Gateway', 'icon': 'ti-credit-card'},
    'verification': {'name': 'KYC & Verification', 'icon': 'ti-file-check'},
    'banking': {'name': 'Banking (AEPS/DMT – Payswap only)', 'icon': 'ti-building-bank'},
    'bbps': {'name': 'BBPS (Bill Pay)', 'icon': 'ti-receipt'},
    'communication': {'name': 'SMS / Communication', 'icon': 'ti-message'},
    'esign': {'name': 'E-Signature', 'icon': 'ti-signature'},
    'other': {'name': 'Other Vendors', 'icon': 'ti-building-store'},
}

# Map vendor code -> category key
VENDOR_TO_CATEGORY = {
    'cashfree_pg': 'payment',
    'cashfree': 'verification',
    'instantpay': 'verification',
    'euronet': 'bbps',
    'mobikwik': 'bbps',
    'kaleyra': 'communication',
    'leegality': 'esign',
}

# Market / Service catalog: service_code -> list of vendor codes (AEPS/DMT removed)
SERVICE_VENDORS = {
    'bbps': ['euronet', 'mobikwik'],
    'kyc': ['cashfree', 'instantpay'],
    'sms': ['kaleyra'],
    'payment': ['cashfree_pg'],
}

SERVICE_DISPLAY_NAMES = {
    'bbps': 'BBPS (Bill Payment)',
    'kyc': 'KYC & Verification',
    'sms': 'SMS & OTP',
    'payment': 'Payment Gateway',
}


# Default auth headers for API-key based APIs
API_KEY_AUTH_HEADERS = [
    {"name": "X-Api-Key", "value": "", "required": True, "description": "API key (or use Authorization: Bearer <key>)"},
    {"name": "Authorization", "value": "Bearer ", "required": False, "description": "Alternative: Bearer <api_key>"},
]


def _path_params_from_path(path):
    """Extract path param names from path e.g. /api/v2/vouchers/<voucher_code>/balance/ -> [voucher_code]"""
    names = re.findall(r"<([a-zA-Z_][a-zA-Z0-9_]*)>", path)
    return [{"name": n, "value": "", "in": "path", "required": True, "description": "Replace in URL"} for n in names]


def _endpoint_headers(collection_id, endpoint_path):
    """Return required/default headers for this collection/endpoint. All APIs get Content-Type and auth option."""
    # Backward compatible wrapper: keep signature but treat "v1-" collections as internal unless marked in id.
    base_headers = [{"name": "Content-Type", "value": "application/json", "required": True, "description": "JSON body"}]
    # API-key based APIs (API key required)
    if collection_id.startswith("v1-vendor-") or collection_id.startswith("v1-api-key-"):
        if "/health" in endpoint_path or "/public" in endpoint_path:
            return base_headers + [{"name": "X-Api-Key", "value": "", "required": False, "description": "Optional API key"}]
        return base_headers + list(API_KEY_AUTH_HEADERS)
    # Internal APIs (session/cookie); include optional API key too (Explorer pre-fills)
    return base_headers + [
        {"name": "X-Api-Key", "value": "", "required": False, "description": "Optional API key"},
        {"name": "Authorization", "value": "Bearer ", "required": False, "description": "Bearer token"},
    ]


def _endpoint_params(path):
    """Return path/query params for this endpoint (path params inferred from URL)."""
    return _path_params_from_path(path)


def _normalize_endpoint(ep, collection_id):
    """Ensure endpoint has headers and params with required/default values."""
    out = dict(ep)
    if "headers" not in out:
        out["headers"] = _endpoint_headers(collection_id, ep.get("path", ""))
    if "params" not in out:
        out["params"] = _endpoint_params(ep.get("path", ""))
    return out


def _normalize_collection(coll):
    """Ensure all endpoints in collection have headers and params."""
    out = dict(coll)
    out["endpoints"] = [_normalize_endpoint(ep, out.get("id", "")) for ep in out["endpoints"]]
    return out


def get_all_collections():
    """
    Return all collections for the Postman-style API Explorer.
    Each collection has: id, name, icon, description, endpoints.
    Each endpoint has: method, path, title, description, sample_body (JSON string or None),
    headers [{ name, value, required, description? }], params [{ name, value, in, required, description? }].
    """
    raw = [
        # -------------------------------------------------------------------------
        # API v1 (Internal)
        # -------------------------------------------------------------------------
        {
            "id": "v1-health",
            "name": "API v1 – Health & Logging",
            "icon": "ti-heartbeat",
            "description": "Internal API v1 – health and logging.",
            "base": "/api/v1",
            "endpoints": [
                {"method": "GET", "path": "/api/v1/health/", "title": "Health Check", "description": "API availability.", "sample_body": None, "sample_response": '{"status": "ok", "message": "API available"}'},
                {"method": "POST", "path": "/api/v1/logging/track-click/", "title": "Track Click", "description": "Log frontend click.", "sample_body": '{"element": "button", "page": "/dashboard"}'},
                {"method": "POST", "path": "/api/v1/logging/bulk/", "title": "Log Bulk Events", "description": "Bulk log events.", "sample_body": '{"events": []}'},
            ],
        },
        {
            "id": "v1-dashboard",
            "name": "API v1 – Dashboard & Analytics",
            "icon": "ti-chart-bar",
            "description": "Dashboard and analytics endpoints.",
            "base": "/api/v1",
            "endpoints": [
                {"method": "GET", "path": "/api/v1/dashboard/overview/", "title": "Dashboard Overview", "description": "Overview stats.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/dashboard/agent-performance/", "title": "Agent Performance", "description": "Agent performance metrics.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/dashboard/department-stats/", "title": "Department Stats", "description": "Department statistics.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/analytics/tickets-by-status/", "title": "Tickets by Status", "description": "Tickets grouped by status.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/analytics/resolution-time/", "title": "Resolution Time", "description": "Resolution time analytics.", "sample_body": None},
            ],
        },
        {
            "id": "v1-vouchers",
            "name": "API v1 – Gift Vouchers (Portal / Session)",
            "icon": "ti-gift",
            "description": "Same Gift Voucher product. These endpoints are used by portal/admin UI (session auth) + reports.",
            "base": "/api/v1",
            "endpoints": [
                {"method": "POST", "path": "/api/v1/vouchers/issue/single/", "title": "Issue Single", "description": "Issue single voucher.", "sample_body": '{"brand_id": 1, "amount": "500.00", "mobile_number": "9876543210"}'},
                {"method": "POST", "path": "/api/v1/vouchers/issue/bulk/", "title": "Issue Bulk", "description": "Bulk issue vouchers.", "sample_body": '{"brand_id": 1, "denominations": {"500": {"quantity": 10}}}'},
                {"method": "GET", "path": "/api/v1/vouchers/issue/bulk/<batch_id>/status/", "title": "Bulk Status", "description": "Bulk issuance status.", "sample_body": None},
                {"method": "POST", "path": "/api/v1/vouchers/redeem/pin/", "title": "Redeem PIN", "description": "Redeem by PIN.", "sample_body": '{"voucher_code": "XXXX", "pin": "1234"}'},
                {"method": "POST", "path": "/api/v1/vouchers/redeem/otp/request/", "title": "Redeem OTP Request", "description": "Request OTP for redemption.", "sample_body": '{"voucher_code": "XXXX"}'},
                {"method": "POST", "path": "/api/v1/vouchers/redeem/otp/verify/", "title": "Redeem OTP Verify", "description": "Verify OTP and redeem.", "sample_body": '{"voucher_code": "XXXX", "verification_id": "...", "otp": "123456"}'},
                {"method": "POST", "path": "/api/v1/vouchers/pin/change/request/", "title": "PIN Change Request", "description": "Request PIN change OTP.", "sample_body": "{}"},
                {"method": "POST", "path": "/api/v1/vouchers/pin/change/verify/", "title": "PIN Change Verify", "description": "Verify OTP and set new PIN.", "sample_body": '{"verification_id": "...", "otp": "123456", "new_pin": "5678"}'},
                {"method": "GET", "path": "/api/v1/vouchers/balance/", "title": "Voucher Balance", "description": "Get balance (query params).", "sample_body": None},
                {"method": "GET", "path": "/api/v1/vouchers/reports/issuance/", "title": "Issuance Report", "description": "Issuance report.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/vouchers/reports/redemption/", "title": "Redemption Report", "description": "Redemption report.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/vouchers/reports/outstanding/", "title": "Outstanding Report", "description": "Outstanding balance report.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/vouchers/batches/<batch_id>/export/", "title": "Batch Export", "description": "Export batch vouchers.", "sample_body": None},
            ],
        },
        {
            "id": "v1-tickets",
            "name": "API v1 – Tickets & Resources",
            "icon": "ti-ticket",
            "description": "Departments, agents, tickets (ViewSet CRUD).",
            "base": "/api/v1",
            "endpoints": [
                {"method": "GET", "path": "/api/v1/departments/", "title": "List Departments", "description": "List departments.", "sample_body": None},
                {"method": "POST", "path": "/api/v1/departments/", "title": "Create Department", "description": "Create department.", "sample_body": '{"name": "Support"}'},
                {"method": "GET", "path": "/api/v1/departments/<id>/", "title": "Department Detail", "description": "Get department.", "sample_body": None},
                {"method": "PUT", "path": "/api/v1/departments/<id>/", "title": "Update Department", "description": "Full update.", "sample_body": '{"name": "Support"}'},
                {"method": "PATCH", "path": "/api/v1/departments/<id>/", "title": "Patch Department", "description": "Partial update.", "sample_body": '{"name": "Support"}'},
                {"method": "DELETE", "path": "/api/v1/departments/<id>/", "title": "Delete Department", "description": "Delete department.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/agents/", "title": "List Agents", "description": "List agents.", "sample_body": None},
                {"method": "POST", "path": "/api/v1/agents/", "title": "Create Agent", "description": "Create agent.", "sample_body": '{"user_id": 1, "department_id": 1}'},
                {"method": "GET", "path": "/api/v1/agents/<id>/", "title": "Agent Detail", "description": "Get agent.", "sample_body": None},
                {"method": "PUT", "path": "/api/v1/agents/<id>/", "title": "Update Agent", "description": "Full update.", "sample_body": '{"user_id": 1, "department_id": 1}'},
                {"method": "PATCH", "path": "/api/v1/agents/<id>/", "title": "Patch Agent", "description": "Partial update.", "sample_body": "{}"},
                {"method": "DELETE", "path": "/api/v1/agents/<id>/", "title": "Delete Agent", "description": "Delete agent.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/tickets/", "title": "List Tickets", "description": "List tickets.", "sample_body": None},
                {"method": "POST", "path": "/api/v1/tickets/", "title": "Create Ticket", "description": "Create ticket.", "sample_body": '{"subject": "Issue", "body": "Details", "department_id": 1}'},
                {"method": "GET", "path": "/api/v1/tickets/<id>/", "title": "Ticket Detail", "description": "Get ticket.", "sample_body": None},
                {"method": "PUT", "path": "/api/v1/tickets/<id>/", "title": "Update Ticket", "description": "Full update.", "sample_body": '{"status": "resolved"}'},
                {"method": "PATCH", "path": "/api/v1/tickets/<id>/", "title": "Patch Ticket", "description": "Partial update.", "sample_body": '{"status": "resolved"}'},
                {"method": "DELETE", "path": "/api/v1/tickets/<id>/", "title": "Delete Ticket", "description": "Delete ticket.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/vouchers/brands/", "title": "List Brands", "description": "List voucher brands.", "sample_body": None},
                {"method": "POST", "path": "/api/v1/vouchers/brands/", "title": "Create Brand", "description": "Create brand.", "sample_body": '{"name": "Brand A"}'},
                {"method": "GET", "path": "/api/v1/vouchers/brands/<id>/", "title": "Brand Detail", "description": "Get brand.", "sample_body": None},
                {"method": "PUT", "path": "/api/v1/vouchers/brands/<id>/", "title": "Update Brand", "description": "Full update.", "sample_body": '{"name": "Brand A"}'},
                {"method": "PATCH", "path": "/api/v1/vouchers/brands/<id>/", "title": "Patch Brand", "description": "Partial update.", "sample_body": "{}"},
                {"method": "DELETE", "path": "/api/v1/vouchers/brands/<id>/", "title": "Delete Brand", "description": "Delete brand.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/vouchers/clients/", "title": "List Clients", "description": "List voucher clients.", "sample_body": None},
                {"method": "POST", "path": "/api/v1/vouchers/clients/", "title": "Create Client", "description": "Create client.", "sample_body": '{"name": "Client A"}'},
                {"method": "GET", "path": "/api/v1/vouchers/clients/<id>/", "title": "Client Detail", "description": "Get client.", "sample_body": None},
                {"method": "PUT", "path": "/api/v1/vouchers/clients/<id>/", "title": "Update Client", "description": "Full update.", "sample_body": '{"name": "Client A"}'},
                {"method": "PATCH", "path": "/api/v1/vouchers/clients/<id>/", "title": "Patch Client", "description": "Partial update.", "sample_body": "{}"},
                {"method": "DELETE", "path": "/api/v1/vouchers/clients/<id>/", "title": "Delete Client", "description": "Delete client.", "sample_body": None},
            ],
        },
        # -------------------------------------------------------------------------
        # API v1 (External vendor integrations – show vendor name)
        # These are OUR APIs that call vendors; vendor can be forced via vendor param.
        # -------------------------------------------------------------------------
        {
            "id": "v1-vendor-cashfree-kyc",
            "name": "API v1 – Cashfree (KYC)",
            "icon": "ti-file-check",
            "description": "KYC/Verification APIs routed to Cashfree (API key based).",
            "base": "/api/v1",
            "vendor_code": "cashfree",
            "endpoints": [
                {"method": "POST", "path": "/api/v1/kyc/pan/verify/", "title": "PAN Verify", "description": "Verify PAN (Cashfree).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/kyc/aadhaar/verify/", "title": "Aadhaar Verify", "description": "Verify Aadhaar (Cashfree).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/kyc/bank/verify/", "title": "Bank Verify", "description": "Verify bank account (Cashfree).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/kyc/driving-license/verify/", "title": "Driving License Verify", "description": "Verify DL (Cashfree).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/kyc/voter-id/verify/", "title": "Voter ID Verify", "description": "Verify Voter ID (Cashfree).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/kyc/passport/verify/", "title": "Passport Verify", "description": "Verify passport (Cashfree).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/kyc/gst/verify/", "title": "GST Verify", "description": "Verify GSTIN (Cashfree).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/kyc/face-match/", "title": "Face Match", "description": "Face match (Cashfree).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/kyc/face-liveness/", "title": "Face Liveness", "description": "Face liveness (Cashfree).", "sample_body": None},
                {"method": "GET", "path": "/api/v1/kyc/verifications/<verification_id>/", "title": "Verification Status", "description": "Get verification status (Cashfree).", "sample_body": None},
            ],
        },
        {
            "id": "v1-vendor-instantpay-kyc",
            "name": "API v1 – Instantpay (KYC)",
            "icon": "ti-file-check",
            "description": "KYC/Verification APIs routed to Instantpay (API key based).",
            "base": "/api/v1",
            "vendor_code": "instantpay",
            "endpoints": [
                {"method": "POST", "path": "/api/v1/kyc/pan/verify/", "title": "PAN Verify", "description": "Verify PAN (Instantpay).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/kyc/aadhaar/verify/", "title": "Aadhaar Verify", "description": "Verify Aadhaar (Instantpay).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/kyc/bank/verify/", "title": "Bank Verify", "description": "Verify bank account (Instantpay).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/kyc/driving-license/verify/", "title": "Driving License Verify", "description": "Verify DL (Instantpay).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/kyc/voter-id/verify/", "title": "Voter ID Verify", "description": "Verify Voter ID (Instantpay).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/kyc/passport/verify/", "title": "Passport Verify", "description": "Verify passport (Instantpay).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/kyc/gst/verify/", "title": "GST Verify", "description": "Verify GSTIN (Instantpay).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/kyc/face-match/", "title": "Face Match", "description": "Face match (Instantpay).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/kyc/face-liveness/", "title": "Face Liveness", "description": "Face liveness (Instantpay).", "sample_body": None},
                {"method": "GET", "path": "/api/v1/kyc/verifications/<verification_id>/", "title": "Verification Status", "description": "Get verification status (Instantpay).", "sample_body": None},
            ],
        },
        {
            "id": "v1-vendor-euronet-bbps",
            "name": "API v1 – Euronet (BBPS)",
            "icon": "ti-receipt",
            "description": "BBPS APIs routed to Euronet (API key based).",
            "base": "/api/v1",
            "vendor_code": "euronet",
            "endpoints": [
                {"method": "GET", "path": "/api/v1/bbps/operators/", "title": "Get Operators", "description": "List BBPS operators (Euronet).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/bbps/bill/fetch/", "title": "Fetch Bill", "description": "Fetch bill details (Euronet).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/bbps/bill/pay/", "title": "Pay Bill", "description": "Pay bill (Euronet).", "sample_body": None},
                {"method": "GET", "path": "/api/v1/bbps/bill/status/<ref_id>/", "title": "Payment Status", "description": "Bill payment status (Euronet).", "sample_body": None},
            ],
        },
        {
            "id": "v1-vendor-mobikwik-bbps",
            "name": "API v1 – Mobikwik (BBPS)",
            "icon": "ti-receipt",
            "description": "BBPS APIs routed to Mobikwik (API key based).",
            "base": "/api/v1",
            "vendor_code": "mobikwik",
            "endpoints": [
                {"method": "GET", "path": "/api/v1/bbps/operators/", "title": "Get Operators", "description": "List BBPS operators (Mobikwik).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/bbps/bill/fetch/", "title": "Fetch Bill", "description": "Fetch bill details (Mobikwik).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/bbps/bill/pay/", "title": "Pay Bill", "description": "Pay bill (Mobikwik).", "sample_body": None},
                {"method": "GET", "path": "/api/v1/bbps/bill/status/<ref_id>/", "title": "Payment Status", "description": "Bill payment status (Mobikwik).", "sample_body": None},
            ],
        },
        {
            "id": "v1-vendor-kaleyra-sms",
            "name": "API v1 – Kaleyra (SMS/OTP)",
            "icon": "ti-message",
            "description": "SMS/OTP APIs routed to Kaleyra (API key based).",
            "base": "/api/v1",
            "vendor_code": "kaleyra",
            "endpoints": [
                {"method": "POST", "path": "/api/v1/sms/send/", "title": "Send SMS", "description": "Send SMS (Kaleyra).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/sms/otp/send/", "title": "Send OTP", "description": "Send OTP (Kaleyra).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/sms/otp/verify/", "title": "Verify OTP", "description": "Verify OTP (Kaleyra).", "sample_body": None},
                {"method": "GET", "path": "/api/v1/sms/delivery-status/<message_id>/", "title": "Delivery Status", "description": "Delivery status (Kaleyra).", "sample_body": None},
            ],
        },
        {
            "id": "v1-vendor-cashfree-pg-payments",
            "name": "API v1 – Cashfree PG (Payments)",
            "icon": "ti-credit-card",
            "description": "Payment APIs routed to Cashfree PG (API key based).",
            "base": "/api/v1",
            "vendor_code": "cashfree_pg",
            "endpoints": [
                {"method": "POST", "path": "/api/v1/payments/initiate/", "title": "Initiate Payment", "description": "Create payment order (Cashfree PG).", "sample_body": None},
                {"method": "GET", "path": "/api/v1/payments/<payment_id>/status/", "title": "Payment Status", "description": "Get payment status (Cashfree PG).", "sample_body": None},
                {"method": "POST", "path": "/api/v1/payments/<payment_id>/refund/", "title": "Refund", "description": "Refund payment (Cashfree PG).", "sample_body": None},
                {"method": "GET", "path": "/api/v1/payments/", "title": "List Payments", "description": "List payments (Cashfree PG).", "sample_body": None},
            ],
        },
        {
            "id": "v1-api-key-vouchers",
            "name": "API v1 – Gift Vouchers (API key / App)",
            "icon": "ti-gift",
            "description": "Same Gift Voucher product. These endpoints are for app/service integration (API key auth).",
            "base": "/api/v1",
            "endpoints": [
                {"method": "POST", "path": "/api/v1/vouchers/issue/", "title": "Issue Voucher", "description": "Issue single voucher.", "sample_body": None},
                {"method": "POST", "path": "/api/v1/vouchers/bulk-issue/", "title": "Bulk Issue", "description": "Bulk issue vouchers.", "sample_body": None},
                {"method": "POST", "path": "/api/v1/vouchers/redeem-pin/", "title": "Redeem PIN", "description": "Redeem by PIN.", "sample_body": None},
                {"method": "POST", "path": "/api/v1/vouchers/redeem-otp/request/", "title": "Redeem OTP Request", "description": "Request OTP.", "sample_body": None},
                {"method": "POST", "path": "/api/v1/vouchers/redeem-otp/verify/", "title": "Redeem OTP Verify", "description": "Verify OTP and redeem.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/vouchers/<voucher_code>/balance/", "title": "Voucher Balance", "description": "Get balance for voucher.", "sample_body": None},
                {"method": "POST", "path": "/api/v1/vouchers/<voucher_code>/pin/change/request/", "title": "PIN Change Request", "description": "Request PIN change OTP.", "sample_body": None},
                {"method": "POST", "path": "/api/v1/vouchers/<voucher_code>/pin/change/verify/", "title": "PIN Change Verify", "description": "Verify and set new PIN.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/vouchers/batches/", "title": "List Batches", "description": "List voucher batches.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/vouchers/batches/<batch_id>/", "title": "Batch Detail", "description": "Get batch details.", "sample_body": None},
            ],
        },
        {
            "id": "v1-services",
            "name": "API v1 – Vendors & Services (Internal)",
            "icon": "ti-folder",
            "description": "Internal service orchestration helpers (session auth).",
            "base": "/api/v1",
            "endpoints": [
                {"method": "GET", "path": "/api/v1/vendors/", "title": "List Vendors", "description": "List API vendors.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/vendors/<vendor_code>/", "title": "Vendor Detail", "description": "Get vendor.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/services/", "title": "List Services", "description": "List services.", "sample_body": None},
                {"method": "GET", "path": "/api/v1/services/<service_code>/flow/", "title": "Service Flow", "description": "Get service flow.", "sample_body": None},
            ],
        },
    ]
    return [_normalize_collection(c) for c in raw]
