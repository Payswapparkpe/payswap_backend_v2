"""
Test all API v1 and v2 endpoints and check responses.
Uses API key from --api-key or from env EXPLORER_DEFAULT_API_KEY (auto).
Reports status code, summary table, and flags issues.
"""
import json
import time
from django.core.management.base import BaseCommand
from django.test import Client


def get_api_key_from_env():
    """Load API key from EXPLORER_DEFAULT_API_KEY (env/config)."""
    try:
        from core.config import payswap_config
        key = getattr(payswap_config, "EXPLORER_DEFAULT_API_KEY", None)
        if key is None:
            return None
        if hasattr(key, "get_secret_value"):
            key = key.get_secret_value()
        return (key or "").strip() or None
    except Exception:
        return None


def get_internal_api_key():
    """
    Fallback: read API key from file (e.g. .explorer-api-key in project root).
    Plain keys are not stored in DB; use EXPLORER_DEFAULT_API_KEY in .env or
    put the key in a file and set EXPLORER_API_KEY_FILE or use .explorer-api-key.
    """
    try:
        from django.conf import settings
        path = __import__("os").environ.get("EXPLORER_API_KEY_FILE") or ""
        if not path:
            base = getattr(settings, "BASE_DIR", None)
            if base:
                path = __import__("os").path.join(base, ".explorer-api-key")
        if path and __import__("os").path.isfile(path):
            with open(path, "r") as f:
                line = (f.readline() or "").strip()
                return line or None
    except Exception:
        pass
    return None


# V1 internal/product endpoints: (method, path, minimal_body_for_POST)
API_V1_TESTS = [
    ("GET", "/api/v1/health/", None),
    ("POST", "/api/v1/logging/track-click/", {"event": "test", "url": "/test"}),
    ("POST", "/api/v1/logging/bulk/", {"events": []}),
    ("GET", "/api/v1/dashboard/overview/", None),
    ("GET", "/api/v1/dashboard/agent-performance/", None),
    ("GET", "/api/v1/dashboard/department-stats/", None),
    ("GET", "/api/v1/analytics/tickets-by-status/", None),
    ("GET", "/api/v1/analytics/resolution-time/", None),
    ("GET", "/api/v1/public/", None),
    ("GET", "/api/v1/partner/", None),
    # Partner-style vouchers (v1)
    ("POST", "/api/v1/vouchers/issue/", {"brand_id": 1, "amount": "500.00", "mobile_number": "9876543210"}),
    ("POST", "/api/v1/vouchers/bulk-issue/", {"brand_id": 1, "denominations": {"500": {"quantity": 1}}}),
    ("POST", "/api/v1/vouchers/redeem-pin/", {"voucher_code": "TEST", "pin": "1234"}),
    ("GET", "/api/v1/vouchers/TESTCODE/balance/", None),
    ("GET", "/api/v1/vouchers/batches/", None),
    ("GET", "/api/v1/vouchers/batches/1/", None),
    # KYC v1
    ("POST", "/api/v1/kyc/pan/verify/", {"pan_number": "ABCDE1234F"}),
    ("GET", "/api/v1/kyc/verifications/cf_ver_123/", None),
    # Payments v1
    ("POST", "/api/v1/payments/initiate/", {"amount": "100.00", "currency": "INR", "order_id": "ord_1"}),
    ("GET", "/api/v1/payments/pay_123/status/", None),
    ("GET", "/api/v1/payments/", None),
    # SMS v1
    ("POST", "/api/v1/sms/send/", {"to": "9876543210", "message": "Test"}),
    # BBPS v1
    ("GET", "/api/v1/bbps/operators/", None),
    ("POST", "/api/v1/bbps/bill/fetch/", {"operator_id": "OP1", "customer_id": "CUST1"}),
    # Services
    ("GET", "/api/v1/vendors/", None),
    ("GET", "/api/v1/services/", None),
    ("GET", "/api/v1/services/bbps/flow/", None),
]

# All API v2 endpoints: (method, path, minimal_body_for_POST)
API_V2_TESTS = [
    # Public
    ("GET", "/api/v2/health/", None),
    ("GET", "/api/v2/public/", None),
    # Partner (needs key)
    ("GET", "/api/v2/partner/", None),
    # Vouchers
    ("POST", "/api/v2/vouchers/issue/", {"brand_id": 1, "amount": "500.00", "mobile_number": "9876543210"}),
    ("POST", "/api/v2/vouchers/bulk-issue/", {"brand_id": 1, "denominations": {"500": {"quantity": 1}}}),
    ("POST", "/api/v2/vouchers/redeem-pin/", {"voucher_code": "TEST", "pin": "1234"}),
    ("POST", "/api/v2/vouchers/redeem-otp/request/", {"voucher_code": "TEST"}),
    ("POST", "/api/v2/vouchers/redeem-otp/verify/", {"voucher_code": "TEST", "verification_id": "v1", "otp": "123456"}),
    ("GET", "/api/v2/vouchers/TESTCODE/balance/", None),
    ("POST", "/api/v2/vouchers/TESTCODE/pin/change/request/", {}),
    ("POST", "/api/v2/vouchers/TESTCODE/pin/change/verify/", {"otp": "123456"}),
    ("GET", "/api/v2/vouchers/batches/", None),
    ("GET", "/api/v2/vouchers/batches/1/", None),
    # KYC
    ("POST", "/api/v2/kyc/pan/verify/", {"pan_number": "ABCDE1234F"}),
    ("POST", "/api/v2/kyc/aadhaar/verify/", {"aadhaar_number": "123456789012"}),
    ("POST", "/api/v2/kyc/bank/verify/", {"account_number": "1234567890", "ifsc": "HDFC0001234"}),
    ("POST", "/api/v2/kyc/driving-license/verify/", {"dl_number": "DL123", "dob": "1990-01-01"}),
    ("POST", "/api/v2/kyc/voter-id/verify/", {"voter_id": "VID123"}),
    ("POST", "/api/v2/kyc/passport/verify/", {"passport_number": "A1234567"}),
    ("POST", "/api/v2/kyc/gst/verify/", {"gstin": "12ABCDE1234F1Z5"}),
    ("POST", "/api/v2/kyc/face-match/", {"image1_url": "https://example.com/1.jpg", "image2_url": "https://example.com/2.jpg"}),
    ("POST", "/api/v2/kyc/face-liveness/", {"callback_url": "https://example.com/cb"}),
    ("GET", "/api/v2/kyc/verifications/cf_ver_123/", None),
    # Payments
    ("POST", "/api/v2/payments/initiate/", {"amount": "100.00", "currency": "INR", "order_id": "ord_1"}),
    ("GET", "/api/v2/payments/pay_123/status/", None),
    ("POST", "/api/v2/payments/pay_123/refund/", {"amount": "50.00"}),
    ("GET", "/api/v2/payments/", None),
    # SMS
    ("POST", "/api/v2/sms/send/", {"to": "9876543210", "message": "Test"}),
    ("POST", "/api/v2/sms/otp/send/", {"to": "9876543210"}),
    ("POST", "/api/v2/sms/otp/verify/", {"to": "9876543210", "otp": "123456"}),
    ("GET", "/api/v2/sms/delivery-status/msg_123/", None),
    # BBPS
    ("GET", "/api/v2/bbps/operators/", None),
    ("POST", "/api/v2/bbps/bill/fetch/", {"operator_id": "OP1", "customer_id": "CUST1"}),
    ("POST", "/api/v2/bbps/bill/pay/", {"operator_id": "OP1", "customer_id": "CUST1", "amount": 100}),
    ("GET", "/api/v2/bbps/bill/status/ref_123/", None),
    # Vendors / Services
    ("GET", "/api/v2/vendors/", None),
    ("GET", "/api/v2/vendors/mobikwik/", None),
    ("GET", "/api/v2/services/", None),
    ("GET", "/api/v2/services/bbps/flow/", None),
]


class Command(BaseCommand):
    help = "Test all API v2 endpoints and report status + response issues"

    def add_arguments(self, parser):
        parser.add_argument("--api-key", type=str, default=None, help="API key for auth; if omitted, uses EXPLORER_DEFAULT_API_KEY from env")
        parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
        parser.add_argument("--no-env-key", action="store_true", help="Do not auto-load key from env (test without auth)")
        parser.add_argument("--v1-only", action="store_true", help="Test only v1 endpoints")
        parser.add_argument("--v2-only", action="store_true", help="Test only v2 endpoints")

    def _run_one(self, client, headers, method, path, body):
        t0 = time.perf_counter()
        try:
            if method == "GET":
                r = client.get(path, **headers)
            else:
                r = client.post(
                    path,
                    data=json.dumps(body) if body else "{}",
                    content_type="application/json",
                    **headers,
                )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            status = r.status_code
            try:
                content = r.json() if "application/json" in (r.get("Content-Type") or "") else None
            except Exception:
                content = None
            if content is None:
                content = r.content.decode("utf-8", errors="replace")[:1000]
            response_str = json.dumps(content, default=str, ensure_ascii=False) if isinstance(content, (dict, list)) else str(content)
            return {"method": method, "path": path, "status": status, "elapsed_ms": round(elapsed_ms, 1), "response_preview": response_str[:300], "response": response_str[:2000]}
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return {"method": method, "path": path, "status": "ERROR", "elapsed_ms": round(elapsed_ms, 1), "response_preview": str(e), "response": str(e)}

    def handle(self, *args, **options):
        api_key = options.get("api_key")
        no_env_key = options.get("no_env_key", False)
        out_json = options.get("json")
        v1_only = options.get("v1_only", False)
        v2_only = options.get("v2_only", False)
        if not api_key and not no_env_key:
            api_key = get_api_key_from_env()
            if not api_key:
                api_key = get_internal_api_key()
                key_source = "file (.explorer-api-key or EXPLORER_API_KEY_FILE)" if api_key else "none"
            else:
                key_source = "env (EXPLORER_DEFAULT_API_KEY)"
        else:
            key_source = "--api-key" if api_key else "none"

        client = Client()
        headers = {"HTTP_X_API_EXPLORER": "true"}
        if api_key:
            key = api_key.replace("Bearer ", "").strip()
            headers["HTTP_X_API_KEY"] = key
            headers["HTTP_AUTHORIZATION"] = f"Bearer {key}"

        results = []
        issues = []

        tests = []
        if not v2_only:
            tests.extend([("v1", t) for t in API_V1_TESTS])
        if not v1_only:
            tests.extend([("v2", t) for t in API_V2_TESTS])

        for version, (method, path, body) in tests:
            r = self._run_one(client, headers, method, path, body)
            r["version"] = version
            results.append(r)
            status = r["status"]
            content = r.get("response", "")
            if status == "ERROR":
                issues.append({"path": path, "method": method, "version": version, "issue": "Exception", "error": r.get("response_preview", "")})
            elif isinstance(status, int):
                if status >= 500:
                    issues.append({"path": path, "method": method, "version": version, "issue": "5xx server error", "status": status, "response": r.get("response_preview", "")})
                elif status == 404 and "/health" not in path and "/public" not in path:
                    issues.append({"path": path, "method": method, "version": version, "issue": "404 not found", "status": status})
                elif status not in (400, 401, 403) and status != 200:
                    issues.append({"path": path, "method": method, "version": version, "issue": f"status {status}", "status": status})

        if out_json:
            summary = {"v1_ok": sum(1 for x in results if x.get("version") == "v1" and x.get("status") == 200),
                      "v1_total": sum(1 for x in results if x.get("version") == "v1"),
                      "v2_ok": sum(1 for x in results if x.get("version") == "v2" and x.get("status") == 200),
                      "v2_total": sum(1 for x in results if x.get("version") == "v2"),
                      "issues_count": len(issues)}
            self.stdout.write(json.dumps({"api_key_source": key_source, "summary": summary, "results": results, "issues": issues}, indent=2, default=str))
            return

        # --- Report ---
        v1_results = [x for x in results if x.get("version") == "v1"]
        v2_results = [x for x in results if x.get("version") == "v2"]
        v1_ok = sum(1 for x in v1_results if x.get("status") == 200)
        v2_ok = sum(1 for x in v2_results if x.get("status") == 200)
        v1_4xx = sum(1 for x in v1_results if isinstance(x.get("status"), int) and 400 <= x.get("status") < 500)
        v2_4xx = sum(1 for x in v2_results if isinstance(x.get("status"), int) and 400 <= x.get("status") < 500)
        v1_5xx = sum(1 for x in v1_results if isinstance(x.get("status"), int) and x.get("status") >= 500)
        v2_5xx = sum(1 for x in v2_results if isinstance(x.get("status"), int) and x.get("status") >= 500)
        v1_err = sum(1 for x in v1_results if x.get("status") == "ERROR")
        v2_err = sum(1 for x in v2_results if x.get("status") == "ERROR")

        self.stdout.write(self.style.SUCCESS("=== API test report (v1 + v2) ===\n"))
        self.stdout.write(f"API key: {key_source}\n")
        self.stdout.write("")
        self.stdout.write("Summary:")
        self.stdout.write("  Version   Total   OK (200)   4xx   5xx   ERROR")
        self.stdout.write(f"  v1        {len(v1_results):5}   {v1_ok:5}      {v1_4xx:3}   {v1_5xx:3}   {v1_err:5}")
        self.stdout.write(f"  v2        {len(v2_results):5}   {v2_ok:5}      {v2_4xx:3}   {v2_5xx:3}   {v2_err:5}")
        self.stdout.write("")
        self.stdout.write("Per-endpoint (method, path, status, ms):")
        for r in results:
            status = r["status"]
            if status == 200:
                style = self.style.SUCCESS
            elif status in (401, 403):
                style = self.style.WARNING
            elif isinstance(status, int) and status >= 500:
                style = self.style.ERROR
            else:
                style = lambda x: x
            ms = r.get("elapsed_ms", 0)
            self.stdout.write(style(f"  [{r.get('version','')}] {r['method']:4} {r['path']:52} -> {status}  ({ms}ms)"))

        self.stdout.write("")
        self.stdout.write("--- Response previews (first 400 chars) ---")
        for r in results:
            resp = r.get("response_preview", "")[:400]
            if len(r.get("response", "")) > 400:
                resp = resp + "..."
            self.stdout.write("")
            self.stdout.write(f"  {r['method']} {r['path']} -> {r['status']}")
            self.stdout.write(f"    {resp}")

        self.stdout.write("")
        if issues:
            self.stdout.write(self.style.ERROR("--- Issues ---"))
            for i in issues:
                self.stdout.write(f"  [{i.get('version')}] {i.get('path')} | {i.get('issue')} | {i.get('response', i.get('error', ''))[:100]}")
        else:
            self.stdout.write(self.style.SUCCESS("No 5xx, 404 or exceptions."))
        self.stdout.write("")
