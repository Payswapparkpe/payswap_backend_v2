"""
Ensure a GiftVoucherBrand exists for ParkPe and can issue vouchers.
Creates or updates brand with api_identifier=PARKPE, status=ACTIVE, onboarding_status=APPROVED.
Set PARKPE_VOUCHER_BRAND_ID in .env to the printed brand ID.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from portal.models import GiftVoucherBrand, User


class Command(BaseCommand):
    help = "Ensure ParkPe voucher brand exists and is approved/active for voucher issuance."

    def handle(self, *args, **options):
        brand = GiftVoucherBrand.objects.filter(api_identifier__iexact="PARKPE").first()
        if not brand:
            brand = GiftVoucherBrand.objects.filter(brand_code__iexact="PARKPE").first()
        if not brand:
            # Create new brand
            brand = GiftVoucherBrand(
                brand_code="PARKPE",
                api_identifier="PARKPE",
                brand_name="ParkPe",
                status="ACTIVE",
                onboarding_status="APPROVED",
                onboarding_completed_at=timezone.now(),
            )
            brand.save()
            self.stdout.write(self.style.SUCCESS(f"Created GiftVoucherBrand id={brand.id}, api_identifier=PARKPE"))
        else:
            updated = []
            if brand.status != "ACTIVE":
                brand.status = "ACTIVE"
                updated.append("status=ACTIVE")
            if brand.onboarding_status != "APPROVED":
                brand.onboarding_status = "APPROVED"
                brand.onboarding_completed_at = brand.onboarding_completed_at or timezone.now()
                updated.append("onboarding_status=APPROVED")
            if not brand.api_identifier or brand.api_identifier.upper() != "PARKPE":
                brand.api_identifier = "PARKPE"
                updated.append("api_identifier=PARKPE")
            if updated:
                brand.save(update_fields=["status", "onboarding_status", "onboarding_completed_at", "api_identifier", "updated_at"])
                self.stdout.write(self.style.SUCCESS(f"Updated brand id={brand.id}: {', '.join(updated)}"))
            else:
                self.stdout.write(f"Brand id={brand.id} already ACTIVE and APPROVED.")

        if not brand.can_issue_vouchers():
            self.stdout.write(self.style.WARNING(f"Brand still cannot issue vouchers: is_onboarded={brand.is_onboarded()}, status={brand.status}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"Brand can issue vouchers: id={brand.id}"))

        self.stdout.write("")
        self.stdout.write("In .env set:")
        self.stdout.write(f"  PARKPE_VOUCHER_BRAND_ID={brand.id}")
        self.stdout.write("Then restart the Django server.")
