"""
Management command to test PayPoint AEPS API (Encrypt, optional Balance Enquiry).
Uses PAYPOINT_AEPS_* from .env. Docs: https://docs.paypointindia.co.in/api/paypoint-aeps-api/paypoint/overview
"""
import json
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test PayPoint AEPS API: Encrypt, optional Balance Enquiry (requires IP whitelist)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-balance",
            action="store_true",
            help="Skip Balance Enquiry (only run Encrypt API)",
        )

    def handle(self, *args, **options):
        from portal.services.vendors.paypoint import PayPointAEPSClient

        client = PayPointAEPSClient()

        self.stdout.write("PayPoint AEPS API test")
        self.stdout.write("=" * 60)

        if not client.is_configured():
            self.stdout.write(
                self.style.ERROR(
                    "Not configured. Set PAYPOINT_AEPS_ENABLED=True and "
                    "PAYPOINT_AEPS_USER_CODE, PAYPOINT_AEPS_PASSWORD, "
                    "PAYPOINT_AEPS_IDENTIFICATION_CODE, PAYPOINT_AEPS_KEY in .env. "
                    "Docs: https://docs.paypointindia.co.in/api/paypoint-aeps-api/paypoint/overview"
                )
            )
            return

        self.stdout.write(f"Base URL: {client.base_url}")
        self.stdout.write("")

        # 1. Encrypt API (required before any AEPS request)
        self.stdout.write("1. Encrypt API (get encrypted UserCode, Password, IdentificationCode)")
        try:
            result = client.encrypt(use_cache=False)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   FAILED: {e}"))
            return
        if not result.get("success"):
            self.stdout.write(self.style.ERROR(f"   FAILED: {result.get('error', result)}"))
            if result.get("response"):
                self.stdout.write(f"   Response: {json.dumps(result.get('response', {}), indent=2)}")
            self.stdout.write(self.style.WARNING("   Ensure IP is whitelisted by PayPoint."))
            return
        self.stdout.write(self.style.SUCCESS("   OK – encrypted credentials received"))
        if result.get("data"):
            # Don't print raw encrypted values; just confirm keys exist
            data = result["data"]
            self.stdout.write(f"   Keys: {list(data.keys())}")
        self.stdout.write("")

        # 2. Balance Enquiry (optional – needs test Aadhaar/biometric; often fails without real device)
        if not options.get("skip_balance"):
            self.stdout.write("2. Balance Enquiry (BE) – placeholder Aadhaar/BankIIN/RdRequest")
            self.stdout.write("   (Use real values and IP whitelist for success.)")
            try:
                result = client.balance_enquiry(
                    aadhaar_number="123456789012",
                    mobile_number="9876543210",
                    bank_iin="TESTBANK",
                    rd_request="<biometric_xml_placeholder>",
                    latitude="28.6139",
                    longitude="77.2090",
                )
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"   FAILED: {e}"))
            else:
                if not result.get("success"):
                    self.stdout.write(self.style.WARNING(f"   FAILED: {result.get('error', result)}"))
                    if result.get("response"):
                        self.stdout.write(f"   Response: {json.dumps(result.get('response', {}), indent=2)}")
                else:
                    self.stdout.write(self.style.SUCCESS("   OK"))
                    if result.get("data"):
                        self.stdout.write(f"   Data: {json.dumps(result['data'], indent=2)}")
            self.stdout.write("")
        else:
            self.stdout.write("2. Balance Enquiry (skipped)")
            self.stdout.write("")

        self.stdout.write(self.style.SUCCESS("PayPoint AEPS test completed."))
