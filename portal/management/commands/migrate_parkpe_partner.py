"""
Ensure ParkPe (and optional payswap) exist as partners with API keys, vendors, wallets.
Internal apps only – no api_management.
"""
import logging
import secrets
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from portal.models import ResellerPartner, ApiVendor
from portal.services.api_key_service import APIKeyService
from portal.services.partner_vendor_service import PartnerVendorService
from decimal import Decimal

User = get_user_model()
logger = logging.getLogger(__name__)

PARKPE_PARTNER_CODE = "parkpe"
DEFAULT_PARTNERS = [PARKPE_PARTNER_CODE]

DEFAULT_VENDOR_ASSIGNMENTS = [
    ("bbps", "mobikwik"),
    ("kyc", "cashfree"),
    ("sms", "kaleyra"),
    ("payment", "cashfree_pg"),
]

FULL_PERMISSIONS = {
    "voucher": {"issue": True, "redeem": True, "status": True, "view_sensitive": True},
    "bbps": {"operators": True, "fetch_bill": True, "pay_bill": True, "payment_status": True},
    "kyc": {"pan": True, "aadhaar": True, "bank": True, "driving_license": True, "voter_id": True, "passport": True, "gst": True, "face_match": True, "face_liveness": True, "status": True},
    "sms": {"send": True, "otp_send": True, "otp_verify": True, "delivery_status": True},
    "payment": {"initiate": True, "status": True, "refund": True},
}


class Command(BaseCommand):
    help = "Ensure ParkPe (and optional partners) exist with API key, vendors, wallet"

    def add_arguments(self, parser):
        parser.add_argument(
            "--create-keys",
            action="store_true",
            help="Create an API key for each partner (plain key shown once).",
        )
        parser.add_argument(
            "--create-wallet",
            action="store_true",
            help="Create Wallet for parkpe and attach (for balance checks).",
        )
        parser.add_argument(
            "--partners",
            type=str,
            default="parkpe",
            help="Comma-separated partner_code list to ensure and seed subscriptions (e.g. parkpe,INTERNAL).",
        )
        parser.add_argument(
            "--assign-vendors",
            action="store_true",
            help="Assign default vendors to parkpe (bbps->mobikwik, etc.).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print what would be done; do not write DB.",
        )

    def handle(self, *args, **options):
        create_keys = options["create_keys"]
        create_wallet = options["create_wallet"]
        assign_vendors = options["assign_vendors"]
        dry_run = options["dry_run"]
        partner_codes = [p.strip() for p in options["partners"].split(",") if p.strip()]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN – no changes will be written."))

        with transaction.atomic():
            if dry_run:
                transaction.set_rollback(True)

            partners_created = []
            for partner_code in partner_codes:
                partner, created = ResellerPartner.objects.get_or_create(
                    partner_code=partner_code,
                    defaults={
                        "company_name": partner_code.capitalize(),
                        "contact_person": f"{partner_code} Platform",
                        "email": f"{partner_code}-partner@payswap.in",
                        "phone": "0000000000",
                        "business_type": "PRIVATE_LTD",
                        "address": f"{partner_code} – Payswap Engine Partner",
                        "status": "ACTIVE",
                        "onboarding_status": "APPROVED",
                    },
                )
                if created:
                    partners_created.append(partner_code)
                    self.stdout.write(self.style.SUCCESS(f"Created ResellerPartner: {partner_code}"))
                else:
                    self.stdout.write(f"ResellerPartner already exists: {partner_code}")

                if partner_code == PARKPE_PARTNER_CODE:
                    if create_keys:
                        if not dry_run:
                            admin = User.objects.filter(is_superuser=True).first() or User.objects.filter(is_staff=True).first()
                            api_key_obj, plain_key, _ = APIKeyService.create_api_key(
                                partner=partner,
                                key_name="ParkPe App",
                                key_type="LIVE",
                                permissions=FULL_PERMISSIONS,
                                rate_limits={},
                                created_by=admin,
                            )
                            self.stdout.write(
                                self.style.SUCCESS(f"Created API key for ParkPe. Store securely (shown once): {plain_key}")
                            )
                            self.stdout.write("Use as X-API-Key or Authorization: Bearer <key> for Engine API calls.")
                        else:
                            self.stdout.write("[DRY RUN] Would create API key for ParkPe.")
                    if assign_vendors and not dry_run:
                        for service_code, vendor_code in DEFAULT_VENDOR_ASSIGNMENTS:
                            vendor = ApiVendor.objects.filter(code=vendor_code, is_active=True).first()
                            if not vendor:
                                self.stdout.write(self.style.WARNING(f'Vendor "{vendor_code}" not found; skip {service_code}.'))
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
                    if (create_wallet or create_keys) and partner_code == PARKPE_PARTNER_CODE and not partner.wallet_id and not dry_run:
                        from portal.models import Role, Wallet
                        wallet_user = User.objects.filter(username="parkpe_wallet").first()
                        if not wallet_user:
                            role = Role.objects.filter(code="employee").first() or Role.objects.first()
                            if role:
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
                                defaults={"balance": Decimal("0"), "currency": "INR", "status": "active"},
                            )
                            partner.wallet = wallet
                            partner.save(update_fields=["wallet"])
                            self.stdout.write(self.style.SUCCESS("Created/attached Wallet for ParkPe."))

        self.stdout.write(self.style.SUCCESS("migrate_parkpe_partner completed."))
