"""
Assign default vendors to existing partners that have no vendor assignments.

Run: python manage.py assign_default_vendors

Default assignments (same for all partners that have none):
- bbps -> mobikwik
- aeps -> paypoint
- dmt -> paypoint_dmt
- kyc -> cashfree
- sms -> kaleyra
- payment -> cashfree_pg

Only partners with status=ACTIVE and no existing assignment for a service get the default.
"""
import logging
from django.core.management.base import BaseCommand
from django.db import transaction

from portal.models import ResellerPartner, ApiVendor, PartnerVendorAssignment
from portal.services.partner_vendor_service import PartnerVendorService

logger = logging.getLogger(__name__)

DEFAULT_VENDOR_ASSIGNMENTS = [
    ('bbps', 'mobikwik'),
    ('aeps', 'paypoint'),
    ('dmt', 'paypoint_dmt'),
    ('kyc', 'cashfree'),
    ('sms', 'kaleyra'),
    ('payment', 'cashfree_pg'),
]


class Command(BaseCommand):
    help = 'Assign default vendors to existing partners that have no vendor assignments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--partner',
            type=str,
            help='Only process this partner (partner_code)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be assigned without making changes',
        )

    def handle(self, *args, **options):
        partner_code = options.get('partner')
        dry_run = options.get('dry_run', False)

        partners = ResellerPartner.objects.filter(status='ACTIVE')
        if partner_code:
            partners = partners.filter(partner_code=partner_code)
        if not partners.exists():
            self.stdout.write(self.style.WARNING('No active partners found.'))
            return

        vendor_by_code = {}
        for service_code, vendor_code in DEFAULT_VENDOR_ASSIGNMENTS:
            v = ApiVendor.objects.filter(code=vendor_code, is_active=True).first()
            if not v:
                self.stdout.write(
                    self.style.WARNING(
                        f'Vendor "{vendor_code}" not found; run seed_vendor_apis. Skipping {service_code}.'
                    )
                )
            else:
                vendor_by_code[(service_code, vendor_code)] = v

        if dry_run:
            self.stdout.write('Dry run – no changes will be made.')

        with transaction.atomic():
            for partner in partners:
                for service_code, vendor_code in DEFAULT_VENDOR_ASSIGNMENTS:
                    key = (service_code, vendor_code)
                    if key not in vendor_by_code:
                        continue
                    has = PartnerVendorAssignment.objects.filter(
                        partner=partner,
                        service_code=service_code,
                        is_active=True,
                    ).exists()
                    if has:
                        continue
                    vendor = vendor_by_code[key]
                    if dry_run:
                        self.stdout.write(
                            f'Would assign {vendor_code} -> {service_code} for {partner.partner_code}'
                        )
                    else:
                        PartnerVendorService.assign_vendor_to_partner(
                            partner=partner,
                            service_code=service_code,
                            vendor=vendor,
                            is_primary=True,
                            priority=1,
                            assigned_by=None,
                        )
                        self.stdout.write(
                            f'Assigned {vendor_code} -> {service_code} for {partner.partner_code}'
                        )

        if dry_run:
            self.stdout.write(self.style.SUCCESS('Dry run finished.'))
        else:
            self.stdout.write(self.style.SUCCESS('assign_default_vendors completed.'))
