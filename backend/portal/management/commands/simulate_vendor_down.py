"""
Simulate vendor down: optional test that failover or graceful degradation works.
Run: python manage.py simulate_vendor_down [--dry-run]
In dry-run only prints what would be tested (e.g. which partner/vendor would be used for failover).
"""
import time
from django.core.management.base import BaseCommand
from portal.models import ResellerPartner, PartnerVendorAssignment
from portal.services.partner_vendor_service import PartnerVendorService


class Command(BaseCommand):
    help = "Simulate vendor down: verify partner has failover vendors (dry-run only, no actual toggle)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=True, help="Only report (default).")

    def handle(self, *args, **options):
        start = time.time()
        try:
            self._handle_impl(*args, **options)
        except Exception as e:
            raise

    def _handle_impl(self, *args, **options):
        self.stdout.write("Simulating vendor-down check (dry-run): listing partners with multiple vendors per service.")
        for partner in ResellerPartner.objects.filter(status="ACTIVE").select_related("wallet")[:20]:
            by_svc = PartnerVendorService.get_assignments_for_partner(partner)
            multi = {s: len(v) for s, v in by_svc.items() if len(v) > 1}
            if multi:
                self.stdout.write(f"  {partner.partner_code}: failover available for {list(multi.keys())}")
            else:
                self.stdout.write(f"  {partner.partner_code}: single vendor per service (no failover)")
        self.stdout.write(self.style.SUCCESS("simulate_vendor_down done. No vendors were actually disabled."))
