"""
Ensure ParkPe exists as a ResellerPartner and optionally create API key and assign vendors.

Run: python manage.py ensure_parkpe_partner [--create-key] [--assign-vendors] [--create-wallet]

Part of Payswap API Governance Platform: ParkPe is treated as a first-class partner.
Use the created API key in ParkPe Angular as X-API-Key (environment.apiKey) for all
Engine API calls to /api/connect, /api/bbps, /api/payment, /api/voucher.

- Creates ResellerPartner with partner_code=parkpe if not exists (ACTIVE, APPROVED).
- --create-key: Create an API key for ParkPe (full service permissions). Output plain key once.
- --assign-vendors: Assign default vendors (bbps->mobikwik, etc.) for ParkPe.
- --create-wallet: Create a Wallet for ParkPe and attach to partner (optional; for balance checks).

Prerequisites: seed_vendor_apis (for --assign-vendors).
"""
import logging
import secrets
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

from portal.models import ResellerPartner, ApiVendor, Wallet
from portal.services.api_key_service import APIKeyService
from portal.services.partner_vendor_service import PartnerVendorService
from decimal import Decimal

User = get_user_model()
logger = logging.getLogger(__name__)

PARKPE_PARTNER_CODE = "parkpe"

DEFAULT_VENDOR_ASSIGNMENTS = [
    ("bbps", "mobikwik"),
    ("kyc", "cashfree"),
    ("sms", "kaleyra"),
    ("payment", "cashfree_pg"),
]

FULL_PERMISSIONS = {
    "voucher": {"issue": True, "redeem": True, "status": True, "view_sensitive": True},
    "bbps": {"operators": True, "fetch_bill": True, "pay_bill": True, "payment_status": True},
    "kyc": {
        "pan": True,
        "aadhaar": True,
        "bank": True,
        "driving_license": True,
        "voter_id": True,
        "passport": True,
        "gst": True,
        "face_match": True,
        "face_liveness": True,
        "status": True,
    },
    "sms": {"send": True, "otp_send": True, "otp_verify": True, "delivery_status": True},
    "payment": {"initiate": True, "status": True, "refund": True},
}


class Command(BaseCommand):
    help = "Ensure ParkPe exists as ResellerPartner; optionally create API key and assign vendors"

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-key",
            action="store_true",
            help="Create an API key for ParkPe (store plain key securely; shown once)",
        )
        parser.add_argument(
            "--assign-vendors",
            action="store_true",
            help="Assign default vendors (bbps, kyc, sms, payment) to ParkPe",
        )
        parser.add_argument(
            "--create-wallet",
            action="store_true",
            help="Create a Wallet for ParkPe and attach to partner (for balance checks)",
        )

    def handle(self, *args, **options):
        create_key = options["create_key"]
        assign_vendors = options["assign_vendors"]
        create_wallet = options["create_wallet"]

        with transaction.atomic():
            partner, created = ResellerPartner.objects.get_or_create(
                partner_code=PARKPE_PARTNER_CODE,
                defaults={
                    "company_name": "ParkPe",
                    "contact_person": "ParkPe Platform",
                    "email": "parkpe-partner@payswap.in",
                    "phone": "0000000000",
                    "business_type": "PRIVATE_LTD",
                    "address": "ParkPe – Payswap Engine Partner",
                    "status": "ACTIVE",
                    "onboarding_status": "APPROVED",
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created ResellerPartner: {PARKPE_PARTNER_CODE}"))
            else:
                self.stdout.write(f"ResellerPartner already exists: {PARKPE_PARTNER_CODE}")

            if create_key:
                admin_user = User.objects.filter(is_superuser=True).first() or User.objects.filter(is_staff=True).first()
                api_key_obj, plain_key, plain_secret = APIKeyService.create_api_key(
                    partner=partner,
                    key_name="ParkPe App",
                    key_type="LIVE",
                    permissions=FULL_PERMISSIONS,
                    rate_limits={},
                    created_by=admin_user,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created API key for ParkPe. Store securely (shown once): {plain_key}"
                    )
                )
                self.stdout.write("Use this key as X-API-Key or Authorization: Bearer <key> for Engine API calls.")

            if assign_vendors:
                for service_code, vendor_code in DEFAULT_VENDOR_ASSIGNMENTS:
                    vendor = ApiVendor.objects.filter(code=vendor_code, is_active=True).first()
                    if not vendor:
                        self.stdout.write(
                            self.style.WARNING(
                                f'Vendor "{vendor_code}" not found; run seed_vendor_apis. Skipping {service_code}.'
                            )
                        )
                        continue
                    PartnerVendorService.assign_vendor_to_partner(
                        partner=partner,
                        service_code=service_code,
                        vendor=vendor,
                        is_primary=True,
                        priority=1,
                        assigned_by=User.objects.filter(is_superuser=True).first(),
                    )
                    self.stdout.write(f"Assigned {vendor_code} -> {service_code} for ParkPe")

            if create_wallet and not partner.wallet_id:
                from portal.models import Role
                wallet_user = User.objects.filter(username="parkpe_wallet").first()
                if not wallet_user:
                    role = Role.objects.filter(code="employee").first() or Role.objects.first()
                    if not role:
                        self.stdout.write(self.style.WARNING("No Role found; run setup_roles. Skipping wallet creation."))
                    else:
                        wallet_user = User.objects.create_user(
                            username="parkpe_wallet",
                            password=secrets.token_urlsafe(48),
                            role_code=role.code,
                            role=role,
                        )
                        wallet_user.set_unusable_password()
                        wallet_user.save()
                if wallet_user:
                    wallet, w_created = Wallet.objects.get_or_create(
                        user=wallet_user,
                        defaults={
                            "balance": Decimal("0"),
                            "currency": "INR",
                            "status": "active",
                        },
                    )
                    partner.wallet = wallet
                    partner.save(update_fields=["wallet"])
                    if w_created:
                        self.stdout.write(self.style.SUCCESS("Created Wallet for ParkPe and attached to partner."))
                    else:
                        self.stdout.write("Wallet already existed; attached to ParkPe partner.")

        self.stdout.write(self.style.SUCCESS("ensure_parkpe_partner completed."))
