"""
Management command to test Mobikwik BBPS API (Token, Balance, Operators).
Uses MOBIKWIK_BBPS_* from .env, or pass --client-id and --client-secret for a one-off test.
"""
import json
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Test Mobikwik BBPS API: Token Generation, Balance Check, Operators"

    def add_arguments(self, parser):
        parser.add_argument(
            "--client-id",
            type=str,
            default=None,
            help="Mobikwik BBPS Client ID (overrides env)",
        )
        parser.add_argument(
            "--client-secret",
            type=str,
            default=None,
            help="Mobikwik BBPS Client Secret (overrides env)",
        )
        parser.add_argument(
            "--base-url",
            type=str,
            default=None,
            help="Mobikwik BBPS base URL (overrides env)",
        )
        parser.add_argument(
            "--skip-balance",
            action="store_true",
            help="Skip Balance Check API call",
        )
        parser.add_argument(
            "--skip-operators",
            action="store_true",
            help="Skip Operators API call",
        )
        parser.add_argument(
            "--view-bill",
            action="store_true",
            help="Test View Bill API with Mobikwik-provided samples (success + failure)",
        )
        parser.add_argument(
            "--view-bill-only",
            action="store_true",
            help="Skip Token/Balance/Operators; only run View Bill test",
        )

    def handle(self, *args, **options):
        from portal.services.vendors.mobikwik import MobikwikBBPSClient

        client_id = options.get("client_id")
        client_secret = options.get("client_secret")
        base_url = options.get("base_url")
        view_bill_only = options.get("view_bill_only", False)
        view_bill = options.get("view_bill", False) or view_bill_only

        client = MobikwikBBPSClient(
            client_id=client_id,
            client_secret=client_secret,
            base_url=base_url,
        )
        # Force enabled if credentials passed via args
        if client_id and client_secret:
            client.enabled = True

        self.stdout.write("Mobikwik BBPS API test")
        self.stdout.write("=" * 60)

        if not client.is_configured():
            self.stdout.write(
                self.style.ERROR(
                    "Not configured. Set MOBIKWIK_BBPS_ENABLED=True and "
                    "MOBIKWIK_BBPS_CLIENT_ID, MOBIKWIK_BBPS_CLIENT_SECRET in .env "
                    "or pass --client-id and --client-secret."
                )
            )
            return

        self.stdout.write(f"Base URL: {client.base_url}")
        self.stdout.write(f"Client ID: {client.client_id[:20]}..." if client.client_id and len(client.client_id) > 20 else f"Client ID: {client.client_id}")
        self.stdout.write("")

        if view_bill_only:
            self._run_view_bill_test(client)
            return

        # 1. Token Generation
        self.stdout.write("1. Token Generation API")
        try:
            result = client.get_token()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   FAILED: {e}"))
            return
        if not result.get("success"):
            self.stdout.write(self.style.ERROR(f"   FAILED: {result.get('error', result)}"))
            if result.get("response"):
                self.stdout.write(f"   Response: {json.dumps(result['response'], indent=2)}")
            if "nodename nor servname" in str(result.get("error", "")) or "ConnectError" in str(result.get("error", "")):
                self.stdout.write(self.style.WARNING("   (Network/DNS issue – run from a machine that can reach Mobikwik.)"))
            return
        self.stdout.write(self.style.SUCCESS("   OK – token received"))
        token_preview = (result.get("token") or "")[:20] + "..." if result.get("token") else ""
        self.stdout.write(f"   Token: {token_preview}")
        if result.get("data"):
            self.stdout.write(f"   Data: {json.dumps(result['data'], indent=2)}")
        self.stdout.write("")

        # 2. Balance Check (optional)
        if not options.get("skip_balance"):
            self.stdout.write("2. Balance Check API")
            result = client.balance_check()
            if not result.get("success"):
                self.stdout.write(self.style.WARNING(f"   FAILED: {result.get('error', result)}"))
                if result.get("response"):
                    self.stdout.write(f"   Response: {json.dumps(result.get('response', {}), indent=2)}")
            else:
                self.stdout.write(self.style.SUCCESS("   OK"))
                data = result.get("data") or {}
                self.stdout.write(f"   Data: {json.dumps(data, indent=2)}")
            self.stdout.write("")
        else:
            self.stdout.write("2. Balance Check API (skipped)")
            self.stdout.write("")

        # 3. Operators (optional)
        if not options.get("skip_operators"):
            self.stdout.write("3. Operators API")
            result = client.get_operators(category=None)
            if not result.get("success"):
                self.stdout.write(self.style.WARNING(f"   FAILED: {result.get('error', result)}"))
                if result.get("response"):
                    self.stdout.write(f"   Response: {json.dumps(result.get('response', {}), indent=2)}")
            else:
                data = result.get("data") or {}
                operators = data.get("operators") or data.get("data") or data.get("billers") or []
                count = len(operators) if isinstance(operators, list) else 0
                self.stdout.write(self.style.SUCCESS(f"   OK – {count} operators"))
                if operators and isinstance(operators, list) and len(operators) <= 5:
                    self.stdout.write(f"   Sample: {json.dumps(operators[:3], indent=2)}")
            self.stdout.write("")
        else:
            self.stdout.write("3. Operators API (skipped)")
            self.stdout.write("")

        # 4. View Bill (Mobikwik test samples)
        if view_bill:
            self._run_view_bill_test(client)
        else:
            self.stdout.write("4. View Bill API (skipped; use --view-bill to test)")
            self.stdout.write("")

        self.stdout.write(self.style.SUCCESS("Mobikwik BBPS test completed."))

    def _run_view_bill_test(self, client):
        """Test View Bill with Mobikwik-provided samples (success + failure)."""
        # Mobikwik test samples from UAT email
        VIEW_BILL_SUCCESS = {"cn": "80003948751", "op": "249", "cir": "1", "adParams": {}}
        VIEW_BILL_FAILURE = {"cn": "80003948751", "op": "29", "cir": "1", "adParams": {}}

        self.stdout.write("4. View Bill API (Mobikwik test samples)")
        self.stdout.write("   Success sample: op=249, cn=80003948751, cir=1")
        result = client.view_bill(
            operator_id="249",
            customer_id="80003948751",
            extra_params={"cir": "1"},
        )
        if result.get("success"):
            self.stdout.write(self.style.SUCCESS("   Success case: OK"))
            data = result.get("data") or result.get("bill_details") or {}
            self.stdout.write(f"   Response: {json.dumps(data, indent=2)[:500]}...")
        else:
            self.stdout.write(self.style.WARNING(f"   Success case: {result.get('error', result)}"))
            if result.get("response"):
                self.stdout.write(f"   Response: {json.dumps(result['response'], indent=2)[:400]}")
        self.stdout.write("")

        self.stdout.write("   Failure sample: op=29, cn=80003948751, cir=1")
        result = client.view_bill(
            operator_id="29",
            customer_id="80003948751",
            extra_params={"cir": "1"},
        )
        if not result.get("success"):
            self.stdout.write(self.style.SUCCESS("   Failure case: OK (expected to fail)"))
            self.stdout.write(f"   Error: {result.get('error', '')[:200]}")
        else:
            self.stdout.write(self.style.WARNING("   Failure case: unexpectedly succeeded"))
        self.stdout.write("")
