"""
Create API keys for internal apps (Payswap, Parkpe) and assign default vendors.

Run: python manage.py create_internal_api_keys

- Creates or reuses "Internal Applications" partner (partner_code=INTERNAL).
- Creates API keys for payswap and parkpe with full service permissions.
- Registers each key in InternalAPIKey.
- Assigns default vendors for the internal partner: BBPS (Euronet), AEPS/DMT (PayPoint),
  KYC (Cashfree), SMS (Kaleyra), Payment (Cashfree PG).

Prerequisites: seed_vendor_apis (ApiVendor records must exist).
"""
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

from portal.models import (
    ResellerPartner,
    InternalAPIKey,
    ApiVendor,
)
from portal.services.api_key_service import APIKeyService
from portal.services.partner_vendor_service import PartnerVendorService

User = get_user_model()
logger = logging.getLogger(__name__)

# Default vendor codes per service for internal partner
DEFAULT_VENDOR_ASSIGNMENTS = [
    ('bbps', 'euronet'),
    ('aeps', 'paypoint'),
    ('dmt', 'paypoint_dmt'),
    ('kyc', 'cashfree'),
    ('sms', 'kaleyra'),
    ('payment', 'cashfree_pg'),
]

# Full permissions for internal apps (all services and actions enabled)
INTERNAL_APP_PERMISSIONS = {
    'voucher': {
        'issue': True,
        'redeem': True,
        'status': True,
        'view_sensitive': True,
    },
    'bbps': {
        'operators': True,
        'fetch_bill': True,
        'pay_bill': True,
        'payment_status': True,
    },
    'aeps': {
        'balance_enquiry': True,
        'cash_withdrawal': True,
        'mini_statement': True,
        'transaction_status': True,
        'add_agent': True,
        'agent_auth': True,
    },
    'dmt': {
        'register_sender': True,
        'add_beneficiary': True,
        'remit': True,
        'transaction_status': True,
        'get_beneficiaries': True,
    },
    'kyc': {
        'pan': True,
        'aadhaar': True,
        'bank': True,
        'driving_license': True,
        'voter_id': True,
        'passport': True,
        'gst': True,
        'face_match': True,
        'face_liveness': True,
        'status': True,
    },
    'sms': {
        'send': True,
        'otp_send': True,
        'otp_verify': True,
        'delivery_status': True,
    },
    'payment': {
        'initiate': True,
        'status': True,
        'refund': True,
    },
}


class Command(BaseCommand):
    help = 'Create API keys for Payswap and Parkpe and assign default vendors to internal partner'

    def add_arguments(self, parser):
        parser.add_argument(
            '--environment',
            type=str,
            default='production',
            help='Environment for InternalAPIKey (development, staging, production)',
        )
        parser.add_argument(
            '--skip-vendors',
            action='store_true',
            help='Skip assigning default vendors (only create partner and API keys)',
        )

    def handle(self, *args, **options):
        env = options['environment']
        skip_vendors = options['skip_vendors']

        with transaction.atomic():
            internal_partner, created = ResellerPartner.objects.get_or_create(
                partner_code='INTERNAL',
                defaults={
                    'company_name': 'Internal Applications',
                    'contact_person': 'System',
                    'email': 'system@payswap.in',
                    'phone': '0000000000',
                    'status': 'ACTIVE',
                    'onboarding_status': 'APPROVED',
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS('Created internal partner INTERNAL'))
            else:
                self.stdout.write('Using existing internal partner INTERNAL')

            admin_user = User.objects.filter(is_superuser=True).first()
            if not admin_user:
                admin_user = User.objects.filter(is_staff=True).first()

            for app_name in ['payswap', 'parkpe']:
                existing = InternalAPIKey.objects.filter(app_name=app_name).first()
                if existing and existing.api_key_id:
                    self.stdout.write(
                        f'Internal API key for "{app_name}" already exists (key_id={existing.api_key_id}). '
                        'Skipping. Delete InternalAPIKey and optionally revoke APIKey to recreate.'
                    )
                    continue

                key_name = f'{app_name.title()} App'
                api_key_obj, plain_key, plain_secret = APIKeyService.create_api_key(
                    partner=internal_partner,
                    key_name=key_name,
                    key_type='LIVE',
                    permissions=INTERNAL_APP_PERMISSIONS,
                    rate_limits={},  # No rate limits for internal apps
                    created_by=admin_user,
                )
                InternalAPIKey.objects.update_or_create(
                    app_name=app_name,
                    defaults={
                        'description': f'API key for {app_name.title()} frontend',
                        'api_key': api_key_obj,
                        'environment': env,
                        'is_active': True,
                        'updated_by': admin_user,
                    },
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created API key for {app_name}: {plain_key} (store securely; secret not shown again)'
                    )
                )

            if not skip_vendors:
                for service_code, vendor_code in DEFAULT_VENDOR_ASSIGNMENTS:
                    vendor = ApiVendor.objects.filter(code=vendor_code, is_active=True).first()
                    if not vendor:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Vendor "{vendor_code}" not found; run seed_vendor_apis. Skipping assignment for {service_code}.'
                            )
                        )
                        continue
                    PartnerVendorService.assign_vendor_to_partner(
                        partner=internal_partner,
                        service_code=service_code,
                        vendor=vendor,
                        is_primary=True,
                        priority=1,
                        assigned_by=admin_user,
                    )
                    self.stdout.write(f'Assigned {vendor_code} -> {service_code} for INTERNAL partner')

        self.stdout.write(self.style.SUCCESS('create_internal_api_keys completed.'))
