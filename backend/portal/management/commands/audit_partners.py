"""
Production readiness: audit all ResellerPartners for visibility and completeness.
Ensures parkpe (and other partners) have: API key(s), subscriptions, vendors, wallet (if enabled).
Run: python manage.py audit_partners [--fix] [--partner parkpe]
--fix: auto-repair missing data (creates key/subscriptions/vendors/wallet via migrate_parkpe_partner logic for parkpe).
"""
import logging
import time
from django.core.management.base import BaseCommand
from django.db import transaction

from portal.models import ResellerPartner, APIKey
from portal.services.partner_vendor_service import PartnerVendorService

logger = logging.getLogger(__name__)

PARKPE_CODE = "parkpe"
REQUIRED_SERVICES_FOR_PARKPE = ("bbps", "payment", "voucher", "sms", "kyc")


class Command(BaseCommand):
    help = "Audit partner data (key, subscriptions, vendors, wallet). Use --fix to auto-repair."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fix",
            action="store_true",
            help="Auto-fix missing partner data (calls migrate_parkpe_partner for parkpe).",
        )
        parser.add_argument(
            "--partner",
            type=str,
            default=None,
            help="Audit only this partner_code (default: all ACTIVE).",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output machine-readable JSON summary.",
        )

    def handle(self, *args, **options):
        return self._handle_impl(*args, **options)

    def _handle_impl(self, *args, **options):
        fix = options["fix"]
        partner_filter = options.get("partner")
        as_json = options.get("json")

        partners = ResellerPartner.objects.filter(status="ACTIVE")
        if partner_filter:
            partners = partners.filter(partner_code=partner_filter)
        partners = partners.select_related("wallet").order_by("partner_code")

        issues = []
        fixed = []

        for partner in partners:
            rec = {
                "partner_code": partner.partner_code,
                "has_api_key": False,
                "api_key_count": 0,
                "subscription_count": 0,
                "vendor_assignments": [],
                "has_wallet": bool(getattr(partner, "wallet_id", None)),
                "issues": [],
                "fixed": [],
            }
            # API keys
            keys = list(APIKey.objects.filter(partner=partner, status="ACTIVE"))
            rec["api_key_count"] = len(keys)
            rec["has_api_key"] = len(keys) >= 1
            if not rec["has_api_key"]:
                rec["issues"].append("no_active_api_key")

            rec["subscription_count"] = 0  # api_management removed – internal apps only

            # Vendor assignments (service_codes for which partner has at least one vendor)
            by_svc = PartnerVendorService.get_assignments_for_partner(partner)
            rec["vendor_assignments"] = list(by_svc.keys()) if by_svc else []
            if partner.partner_code == PARKPE_CODE:
                for svc in REQUIRED_SERVICES_FOR_PARKPE:
                    if svc not in rec["vendor_assignments"]:
                        rec["issues"].append(f"missing_vendor:{svc}")

            if rec["issues"]:
                issues.append(rec)
            else:
                if not as_json:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"{partner.partner_code}: OK (keys={rec['api_key_count']}, vendors={len(rec['vendor_assignments'])}, wallet={rec['has_wallet']})"
                        )
                    )
                continue

            if not as_json:
                self.stdout.write(
                    self.style.WARNING(
                        f"{partner.partner_code}: issues={rec['issues']} (keys={rec['api_key_count']})"
                    )
                )

            if fix and partner.partner_code == PARKPE_CODE:
                with transaction.atomic():
                    from django.core.management import call_command
                    fix_args = ["migrate_parkpe_partner", "--partners", PARKPE_CODE]
                    if not rec["has_api_key"]:
                        fix_args.extend(["--create-keys"])
                    if any("missing_vendor" in i for i in rec["issues"]):
                        fix_args.append("--assign-vendors")
                    if not rec["has_wallet"]:
                        fix_args.append("--create-wallet")
                    try:
                        call_command(*fix_args)
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Fix failed for {PARKPE_CODE}: {e}"))
                        continue
                    fixed.append(partner.partner_code)
                    if not as_json:
                        self.stdout.write(self.style.SUCCESS(f"Fixed {partner.partner_code} via migrate_parkpe_partner."))

        if as_json:
            import json
            self.stdout.write(json.dumps({"issues": issues, "fixed": fixed, "ok": len(partners) - len(issues) + len(fixed)}))
            return

        self.stdout.write("")
        if issues:
            self.stdout.write(self.style.WARNING(f"Partners with issues: {len(issues)}"))
            if fix:
                self.stdout.write(self.style.SUCCESS(f"Auto-fixed: {fixed or 'none (run migrate_parkpe_partner manually if needed)'}"))
        else:
            self.stdout.write(self.style.SUCCESS("All audited partners are complete."))
