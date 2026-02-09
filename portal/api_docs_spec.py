"""
REST API documentation spec for Admin API Docs page.
Used by APIDocumentationView. Base URL is e.g. https://yoursite.com/api/v2
"""


def get_api_documentation_spec(base_url):
    """
    Return structured API spec for documentation page.
    base_url: e.g. https://yoursite.com/api/v2 (no trailing slash)
    """
    base = (base_url or "").rstrip("/")
    return [
        {
            "id": "health",
            "name": "Health & Public",
            "icon": "ti-heartbeat",
            "description": "Public endpoints, no authentication required.",
            "endpoints": [
                {
                    "method": "GET",
                    "path": f"{base}/health/",
                    "title": "Health Check",
                    "description": "Check API availability.",
                    "auth": "None",
                    "request_body": None,
                    "response_sample": '{"status": "ok", "timestamp": "..."}',
                },
            ],
        },
        {
            "id": "vouchers",
            "name": "Gift Vouchers",
            "icon": "ti-gift",
            "description": "Issue, redeem, balance, PIN change, and batch operations for gift vouchers.",
            "endpoints": [
                {
                    "method": "POST",
                    "path": f"{base}/vouchers/issue/",
                    "title": "Issue Voucher",
                    "description": "Issue a single gift voucher.",
                    "auth": "API Key (voucher.issue)",
                    "request_body": '{"brand_id": 1, "amount": "500.00", "mobile_number": "9876543210"}',
                    "response_sample": '{"success": true, "data": {"voucher_code": "...", "pin": "...", "reference_number": "..."}}',
                },
                {
                    "method": "POST",
                    "path": f"{base}/vouchers/bulk-issue/",
                    "title": "Bulk Issue Vouchers",
                    "description": "Create a batch of vouchers.",
                    "auth": "API Key (voucher.issue)",
                    "request_body": '{"brand_id": 1, "denominations": {"500": {"quantity": 10}}}',
                    "response_sample": '{"success": true, "data": {"batch_id": 1, "batch_reference": "..."}}',
                },
                {
                    "method": "POST",
                    "path": f"{base}/vouchers/redeem-pin/",
                    "title": "Redeem by PIN",
                    "description": "Redeem voucher using PIN.",
                    "auth": "API Key (voucher.redeem)",
                    "request_body": '{"voucher_code": "XXXX", "pin": "1234"}',
                    "response_sample": '{"success": true, "data": {"status": "redeemed", "amount": "500.00"}}',
                },
                {
                    "method": "POST",
                    "path": f"{base}/vouchers/redeem-otp/request/",
                    "title": "Redeem OTP – Request",
                    "description": "Request OTP for OTP-based redemption.",
                    "auth": "API Key (voucher.redeem)",
                    "request_body": '{"voucher_code": "XXXX"}',
                    "response_sample": '{"success": true, "data": {"verification_id": "..."}}',
                },
                {
                    "method": "POST",
                    "path": f"{base}/vouchers/redeem-otp/verify/",
                    "title": "Redeem OTP – Verify",
                    "description": "Verify OTP and complete redemption.",
                    "auth": "API Key (voucher.redeem)",
                    "request_body": '{"voucher_code": "XXXX", "verification_id": "...", "otp": "123456"}',
                    "response_sample": '{"success": true, "data": {"status": "redeemed"}}',
                },
                {
                    "method": "GET",
                    "path": f"{base}/vouchers/{{voucher_code}}/balance/",
                    "title": "Voucher Balance",
                    "description": "Get balance for a voucher code.",
                    "auth": "API Key (voucher.balance)",
                    "request_body": None,
                    "response_sample": '{"success": true, "data": {"balance": "500.00", "currency": "INR"}}',
                },
                {
                    "method": "POST",
                    "path": f"{base}/vouchers/{{voucher_code}}/pin/change/request/",
                    "title": "PIN Change – Request",
                    "description": "Request OTP for PIN change.",
                    "auth": "API Key (voucher.pin_change)",
                    "request_body": "{}",
                    "response_sample": '{"success": true, "data": {"verification_id": "..."}}',
                },
                {
                    "method": "POST",
                    "path": f"{base}/vouchers/{{voucher_code}}/pin/change/verify/",
                    "title": "PIN Change – Verify",
                    "description": "Verify OTP and set new PIN.",
                    "auth": "API Key (voucher.pin_change)",
                    "request_body": '{"verification_id": "...", "otp": "123456", "new_pin": "5678"}',
                    "response_sample": '{"success": true}',
                },
                {
                    "method": "GET",
                    "path": f"{base}/vouchers/batches/",
                    "title": "List Batches",
                    "description": "List voucher batches for the partner.",
                    "auth": "API Key (voucher.batch_view)",
                    "request_body": None,
                    "response_sample": '{"success": true, "data": {"batches": [...]}}',
                },
                {
                    "method": "GET",
                    "path": f"{base}/vouchers/batches/{{batch_id}}/",
                    "title": "Batch Detail",
                    "description": "Get details of a specific batch.",
                    "auth": "API Key (voucher.batch_view)",
                    "request_body": None,
                    "response_sample": '{"success": true, "data": {"batch_id": 1, "status": "...", "vouchers": [...]}}',
                },
            ],
        },
        {
            "id": "kyc",
            "name": "KYC / Verification",
            "icon": "ti-file-check",
            "description": "Document and identity verification (PAN, Aadhaar, Bank, DL, Voter ID, Passport, GST, Face Match, Face Liveness).",
            "endpoints": [
                {"method": "POST", "path": f"{base}/kyc/pan/verify/", "title": "PAN Verify", "description": "Verify PAN details.", "auth": "API Key (kyc.pan)", "request_body": '{"pan_number": "ABCDE1234F", "name": "Optional"}', "response_sample": '{"success": true, "data": {"name": "...", "status": "valid"}}'},
                {"method": "POST", "path": f"{base}/kyc/aadhaar/verify/", "title": "Aadhaar Verify", "description": "Verify Aadhaar.", "auth": "API Key (kyc.aadhaar)", "request_body": '{"aadhaar_number": "123456789012"}', "response_sample": '{"success": true, "data": {...}}'},
                {"method": "POST", "path": f"{base}/kyc/bank/verify/", "title": "Bank Verify", "description": "Verify bank account.", "auth": "API Key (kyc.bank)", "request_body": '{"account_number": "1234567890", "ifsc_code": "HDFC0001234"}', "response_sample": '{"success": true, "data": {"account_holder": "...", "bank_name": "..."}}'},
                {"method": "POST", "path": f"{base}/kyc/driving-license/verify/", "title": "Driving License Verify", "description": "Verify driving license.", "auth": "API Key (kyc.driving_license)", "request_body": '{"dl_number": "...", "dob": "YYYY-MM-DD"}', "response_sample": '{"success": true, "data": {...}}'},
                {"method": "POST", "path": f"{base}/kyc/voter-id/verify/", "title": "Voter ID Verify", "description": "Verify Voter ID.", "auth": "API Key (kyc.voter_id)", "request_body": '{"voter_id": "..."}', "response_sample": '{"success": true, "data": {...}}'},
                {"method": "POST", "path": f"{base}/kyc/passport/verify/", "title": "Passport Verify", "description": "Verify passport.", "auth": "API Key (kyc.passport)", "request_body": '{"passport_number": "...", "dob": "YYYY-MM-DD"}', "response_sample": '{"success": true, "data": {...}}'},
                {"method": "POST", "path": f"{base}/kyc/gst/verify/", "title": "GST Verify", "description": "Verify GSTIN.", "auth": "API Key (kyc.gst)", "request_body": '{"gstin": "29AAACP2912R1ZR"}', "response_sample": '{"success": true, "data": {...}}'},
                {"method": "POST", "path": f"{base}/kyc/face-match/", "title": "Face Match", "description": "Compare two face images.", "auth": "API Key (kyc.face_match)", "request_body": '{"image1_base64": "...", "image2_base64": "..."}', "response_sample": '{"success": true, "data": {"match": true}}'},
                {"method": "POST", "path": f"{base}/kyc/face-liveness/", "title": "Face Liveness", "description": "Liveness check from face image.", "auth": "API Key (kyc.face_liveness)", "request_body": '{"image_base64": "..."}', "response_sample": '{"success": true, "data": {"liveness": "live"}}'},
                {"method": "GET", "path": f"{base}/kyc/verifications/{{verification_id}}/", "title": "Verification Status", "description": "Get status of a verification request.", "auth": "API Key", "request_body": None, "response_sample": '{"success": true, "data": {"status": "completed", "result": {...}}'},
            ],
        },
        {
            "id": "payments",
            "name": "Payment Gateway",
            "icon": "ti-credit-card",
            "description": "Initiate payment, check status, refund, list payments.",
            "endpoints": [
                {"method": "POST", "path": f"{base}/payments/initiate/", "title": "Initiate Payment", "description": "Create a payment order.", "auth": "API Key (payment.initiate)", "request_body": '{"amount": "100.00", "currency": "INR", "order_id": "ORD001", "customer_email": "..."}', "response_sample": '{"success": true, "data": {"payment_id": "...", "redirect_url": "..."}}'},
                {"method": "GET", "path": f"{base}/payments/{{payment_id}}/status/", "title": "Payment Status", "description": "Get payment status.", "auth": "API Key (payment.status)", "request_body": None, "response_sample": '{"success": true, "data": {"status": "success", "amount": "100.00"}}'},
                {"method": "POST", "path": f"{base}/payments/{{payment_id}}/refund/", "title": "Refund", "description": "Refund a payment.", "auth": "API Key (payment.refund)", "request_body": '{"amount": "50.00", "reason": "Customer request"}', "response_sample": '{"success": true, "data": {"refund_id": "..."}}'},
                {"method": "GET", "path": f"{base}/payments/", "title": "List Payments", "description": "List payments for the partner.", "auth": "API Key (payment.status)", "request_body": None, "response_sample": '{"success": true, "data": {"payments": [...]}}'},
            ],
        },
        {
            "id": "sms",
            "name": "SMS / OTP",
            "icon": "ti-message",
            "description": "Send SMS, OTP send/verify, delivery status.",
            "endpoints": [
                {"method": "POST", "path": f"{base}/sms/send/", "title": "Send SMS", "description": "Send transactional SMS.", "auth": "API Key (sms.send)", "request_body": '{"to": "9876543210", "message": "Hello"}', "response_sample": '{"success": true, "data": {"message_id": "..."}}'},
                {"method": "POST", "path": f"{base}/sms/otp/send/", "title": "Send OTP", "description": "Send OTP to mobile.", "auth": "API Key (sms.otp_send)", "request_body": '{"mobile": "9876543210"}', "response_sample": '{"success": true, "data": {"otp_id": "..."}}'},
                {"method": "POST", "path": f"{base}/sms/otp/verify/", "title": "Verify OTP", "description": "Verify OTP.", "auth": "API Key (sms.otp_verify)", "request_body": '{"mobile": "9876543210", "otp": "123456"}', "response_sample": '{"success": true, "data": {"verified": true}}'},
                {"method": "GET", "path": f"{base}/sms/delivery-status/{{message_id}}/", "title": "Delivery Status", "description": "Get SMS delivery status.", "auth": "API Key (sms.delivery_status)", "request_body": None, "response_sample": '{"success": true, "data": {"status": "delivered"}}'},
            ],
        },
        {
            "id": "bbps",
            "name": "BBPS (Bill Payment)",
            "icon": "ti-receipt",
            "description": "Bharat Bill Payment System – operators, fetch bill, pay bill, payment status.",
            "endpoints": [
                {"method": "GET", "path": f"{base}/bbps/operators/", "title": "Get Operators", "description": "List BBPS operators/billers. Optional query: category=ELECTRICITY.", "auth": "API Key (bbps.operators)", "request_body": None, "response_sample": '{"success": true, "data": {"operators": [...]}}'},
                {"method": "POST", "path": f"{base}/bbps/bill/fetch/", "title": "Fetch Bill", "description": "Fetch bill details for a consumer.", "auth": "API Key (bbps.fetch_bill)", "request_body": '{"operator_id": "OP001", "customer_id": "1234567890"}', "response_sample": '{"success": true, "data": {"bill_details": {"amount": "500", ...}}}'},
                {"method": "POST", "path": f"{base}/bbps/bill/pay/", "title": "Pay Bill", "description": "Pay a bill.", "auth": "API Key (bbps.pay_bill)", "request_body": '{"operator_id": "OP001", "customer_id": "1234567890", "amount": "500.00", "ref_id": "unique-ref-123"}', "response_sample": '{"success": true, "data": {"transaction_id": "...", "status": "SUBMITTED"}}'},
                {"method": "GET", "path": f"{base}/bbps/bill/status/{{ref_id}}/", "title": "Payment Status", "description": "Get payment status by ref_id.", "auth": "API Key (bbps.payment_status)", "request_body": None, "response_sample": '{"success": true, "data": {"ref_id": "...", "status": "SUCCESS"}}'},
            ],
        },
        {
            "id": "aeps",
            "name": "AEPS (Aadhaar Banking)",
            "icon": "ti-fingerprint",
            "description": "Aadhaar Enabled Payment System – balance enquiry, cash withdrawal, mini statement.",
            "endpoints": [
                {"method": "POST", "path": f"{base}/aeps/balance/", "title": "Balance Enquiry", "description": "AEPS balance enquiry (Aadhaar + biometric).", "auth": "API Key (aeps.balance_enquiry)", "request_body": '{"aadhaar_number": "123456789012", "mobile_number": "9876543210", "bank_iin": "...", "rd_request": "<biometric XML>", "latitude": "28.6139", "longitude": "77.2090"}', "response_sample": '{"success": true, "data": {"balance": "5000.00", "rrn": "..."}}'},
                {"method": "POST", "path": f"{base}/aeps/withdrawal/", "title": "Cash Withdrawal", "description": "AEPS cash withdrawal.", "auth": "API Key (aeps.cash_withdrawal)", "request_body": '{"aadhaar_number": "...", "mobile_number": "...", "bank_iin": "...", "rd_request": "...", "amount": "1000.00", "latitude": "...", "longitude": "..."}', "response_sample": '{"success": true, "data": {"transaction_id": "...", "status": "SUBMITTED"}}'},
                {"method": "POST", "path": f"{base}/aeps/mini-statement/", "title": "Mini Statement", "description": "AEPS mini statement.", "auth": "API Key (aeps.mini_statement)", "request_body": '{"aadhaar_number": "...", "mobile_number": "...", "bank_iin": "...", "rd_request": "...", "latitude": "...", "longitude": "..."}', "response_sample": '{"success": true, "data": {"transactions": [...]}}'},
                {"method": "GET", "path": f"{base}/aeps/status/{{ref_id}}/", "title": "Transaction Status", "description": "Get AEPS transaction status.", "auth": "API Key (aeps.transaction_status)", "request_body": None, "response_sample": '{"success": true, "data": {"ref_id": "...", "status": "SUCCESS"}}'},
            ],
        },
    ]
