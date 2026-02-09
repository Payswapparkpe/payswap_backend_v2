"""
Management command to test Euronet BBPS API (Balance Enquiry, Get Billers).
Uses EURONET_BBPS_* from .env. Matches flow in Euronet BBPS/Euronet_BBPS_Postman_Collection.json.
"""
import json
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test Euronet BBPS API: Balance Enquiry, Get Billers (EnService endpoint)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-balance",
            action="store_true",
            help="Skip Balance Enquiry API call",
        )
        parser.add_argument(
            "--skip-billers",
            action="store_true",
            help="Skip Get Billers API call",
        )

    def handle(self, *args, **options):
        from portal.services.vendors.euronet import EuronetBBPSClient

        client = EuronetBBPSClient()

        self.stdout.write("Euronet BBPS API test (EnService)")
        self.stdout.write("=" * 60)

        if not client.is_configured():
            self.stdout.write(
                self.style.ERROR(
                    "Not configured. Set EURONET_BBPS_ENABLED=True and "
                    "EURONET_BBPS_MERCHANT_CODE, EURONET_BBPS_USERNAME, EURONET_BBPS_PASSWORD, "
                    "EURONET_BBPS_STORE_CODE, EURONET_BBPS_AGENT_ID, EURONET_BBPS_SALT in .env. "
                    "See docs/EURONET_BBPS_INTEGRATION.md and Euronet BBPS/Euronet_BBPS_Postman_Collection.json."
                )
            )
            return

        self.stdout.write(f"Base URL: {client.base_url}")
        self.stdout.write(f"Merchant: {client.merchant_code}")
        self.stdout.write("")

        # 1. Balance Enquiry (serviceType BALANCE_ENQUIRY)
        if not options.get("skip_balance"):
            self.stdout.write("1. Balance Enquiry (BALANCE_ENQUIRY)")
            try:
                result = client.balance_check()
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   FAILED: {e}"))
                return
            if not result.get("success"):
                self.stdout.write(self.style.ERROR(f"   FAILED: {result.get('error', result)}"))
                if result.get("response"):
                    self.stdout.write(f"   Response: {json.dumps(result.get('response', {}), indent=2)}")
                return
            self.stdout.write(self.style.SUCCESS("   OK"))
            if result.get("data"):
                self.stdout.write(f"   Data: {json.dumps(result['data'], indent=2)}")
            self.stdout.write("")
        else:
            self.stdout.write("1. Balance Enquiry (skipped)")
            self.stdout.write("")

        # 2. Get Billers (serviceType GET_BILLERS)
        if not options.get("skip_billers"):
            self.stdout.write("2. Get Billers (GET_BILLERS)")
            try:
                result = client.get_operators(category=None)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   FAILED: {e}"))
                return
            if not result.get("success"):
                self.stdout.write(self.style.WARNING(f"   FAILED: {result.get('error', result)}"))
                if result.get("response"):
                    self.stdout.write(f"   Response: {json.dumps(result.get('response', {}), indent=2)}")
            else:
                data = result.get("data") or {}
                billers = data.get("billers") or data.get("operators") or data.get("data") or []
                if isinstance(billers, dict):
                    billers = billers.get("list", billers.get("billers", []))
                count = len(billers) if isinstance(billers, list) else 0
                self.stdout.write(self.style.SUCCESS(f"   OK – {count} billers/operators"))
                if billers and isinstance(billers, list) and len(billers) <= 5:
                    self.stdout.write(f"   Sample: {json.dumps(billers[:3], indent=2)}")
            self.stdout.write("")
        else:
            self.stdout.write("2. Get Billers (skipped)")
            self.stdout.write("")

        self.stdout.write(self.style.SUCCESS("Euronet BBPS test completed."))
