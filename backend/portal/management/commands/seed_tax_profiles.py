"""
Seed default TaxServiceProfile rows (0% / exempt / pass-through) so production matches pre-tax behaviour
until finance updates rates in Hub → Accounting → Tax profiles.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from portal.models import TaxServiceProfile


def _profiles():
    today = timezone.now().date()
    b2c_codes = (
        "bbps",
        "rc_view",
        "voucher_purchase",
        "fastag",
        "parking",
        "challan",
        "rollback",
        "other",
    )
    rows = []
    for code in b2c_codes:
        rows.append(
            {
                "service_code": code,
                "document_subtype": TaxServiceProfile.DOC_B2C,
                "sac_or_hsn": "",
                "gst_rate": Decimal("0"),
                "gst_inclusive": True,
                "is_gst_exempt": True,
                "is_pass_through": code == "bbps",
                "tds_rate": None,
                "effective_from": today,
                "is_active": True,
                "notes": "Seeded default (no GST). Adjust in Accounting → Tax profiles.",
            }
        )
    rows.append(
        {
            "service_code": "partner_commission",
            "document_subtype": TaxServiceProfile.DOC_B2B,
            "sac_or_hsn": "",
            "gst_rate": Decimal("0"),
            "gst_inclusive": False,
            "is_gst_exempt": True,
            "is_pass_through": False,
            "tds_rate": None,
            "effective_from": today,
            "is_active": True,
            "notes": "Seeded B2B commission stub (no GST/TDS until configured).",
        }
    )
    return rows


class Command(BaseCommand):
    help = "Upsert default TaxServiceProfile rows for ParkPe / partner commission."

    def handle(self, *args, **options):
        n = 0
        for fields in _profiles():
            sc = fields.pop("service_code")
            sub = fields.pop("document_subtype")
            obj, created = TaxServiceProfile.objects.update_or_create(
                service_code=sc,
                document_subtype=sub,
                defaults=fields,
            )
            n += 1
            verb = "created" if created else "updated"
            self.stdout.write(self.style.SUCCESS(f"{verb}: {obj}"))
        self.stdout.write(self.style.SUCCESS(f"Done. {n} profile(s)."))
