"""
End-to-end test: Mobikwik BBPS for Parkpe.
Verifies (1) APIProduct mobikwik_bbps is enabled for parkpe, (2) BBPSService with vendor=mobikwik is available and can call operators (or token).
"""
from django.core.management.base import BaseCommand

from api_management.models import APIProduct
from api_management.product_control import is_product_enabled


class Command(BaseCommand):
    help = "Run minimal E2E: Mobikwik BBPS product for Parkpe + service availability."

    def handle(self, *args, **options):
        self.stdout.write("1. Checking APIProduct Mobikwik BBPS for Parkpe...")
        try:
            product = APIProduct.objects.get(
                platform=APIProduct.PLATFORM_PARKPE,
                product_slug="mobikwik_bbps",
            )
            if not product.enabled:
                self.stdout.write(self.style.WARNING("   Mobikwik BBPS is OFF for Parkpe. Turn ON in Dashboard → API Control."))
            else:
                self.stdout.write(self.style.SUCCESS("   Mobikwik BBPS is ON for Parkpe."))
        except APIProduct.DoesNotExist:
            self.stdout.write(self.style.ERROR("   Product mobikwik_bbps for parkpe not found. Run: python manage.py seed_api_products"))
            return

        self.stdout.write("2. Checking product_enabled(platform=parkpe, product_slug=mobikwik_bbps)...")
        # Simulate request with app=parkpe (no real request; pass platform explicitly)
        enabled = is_product_enabled("parkpe", "mobikwik_bbps")
        if not enabled:
            self.stdout.write(self.style.ERROR("   is_product_enabled returned False."))
        else:
            self.stdout.write(self.style.SUCCESS("   is_product_enabled returned True."))

        self.stdout.write("3. Checking BBPSService (Mobikwik) availability...")
        try:
            from portal.services.bbps_service import BBPSService
            service = BBPSService(vendor="mobikwik")
            if not service.is_available():
                self.stdout.write(self.style.WARNING("   Mobikwik BBPS client not configured (check .env MOBIKWIK_BBPS_*)."))
            else:
                self.stdout.write(self.style.SUCCESS("   Mobikwik BBPS client is configured."))
                # Optional: call get_operators (may fail in CI without network/credentials)
                result = service.get_operators(category=None)
                if result.get("success"):
                    self.stdout.write(self.style.SUCCESS(f"   get_operators OK (count: {len(result.get('operators', []))})."))
                else:
                    self.stdout.write(self.style.WARNING(f"   get_operators failed: {result.get('message', 'unknown')}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   Error: {e}"))

        self.stdout.write(self.style.SUCCESS("E2E check done. For full screen flow: Portal → Services → BBPS → Mobikwik (operators, fetch bill, pay, status)."))
