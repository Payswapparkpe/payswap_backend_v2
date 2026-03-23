"""
Export enterprise data for reporting/reconciliation (audited).
Outputs JSON to stdout or file. For use in cron or manual runs.

Usage:
  python manage.py enterprise_export
  python manage.py enterprise_export --format=json --output=exports/enterprise_YYYYMMDD.json
"""
import json
import logging
import time
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Export enterprise data (reporting, reconciliation, settlement summary) for audit."

    def add_arguments(self, parser):
        parser.add_argument("--output", type=str, default=None, help="Write to file (default: stdout).")
        parser.add_argument("--format", type=str, default="json", choices=["json"], help="Output format.")
        parser.add_argument("--days", type=int, default=30, help="Include data for last N days (default 30).")

    def handle(self, *args, **options):
        return self._handle_impl(*args, **options)

    def _handle_impl(self, *args, **options):
        from django.db.models import Sum
        from portal.models import ResellerPartner, ResellerPartnerTransaction, ResellerPartnerSettlement, APIKeyUsageLog

        since = timezone.now() - timedelta(days=options["days"])
        logger.info("enterprise_export started since=%s", since)

        rev = ResellerPartnerTransaction.objects.filter(
            transaction_date__gte=since, transaction_type="REVENUE", status="COMPLETED"
        ).aggregate(s=Sum("amount"))["s"] or 0
        comm = ResellerPartnerTransaction.objects.filter(
            transaction_date__gte=since, transaction_type="COMMISSION", status="COMPLETED"
        ).aggregate(s=Sum("commission_amount"))["s"] or 0
        partner_count = ResellerPartner.objects.filter(status="ACTIVE").count()
        request_count = APIKeyUsageLog.objects.filter(created_at__gte=since).count()
        settlements = list(
            ResellerPartnerSettlement.objects.filter(settlement_period_end__gte=since)
            .values("id", "partner_id", "settlement_period_start", "settlement_period_end", "status", "settlement_amount", "settlement_reference")
            .order_by("-settlement_period_end")[:500]
        )
        from decimal import Decimal
        for s in settlements:
            for k, v in list(s.items()):
                if hasattr(v, "isoformat"):
                    s[k] = v.isoformat()
                elif isinstance(v, Decimal):
                    s[k] = str(v)

        payload = {
            "exported_at": timezone.now().isoformat(),
            "since": since.isoformat(),
            "reporting": {
                "revenue": str(rev),
                "commission": str(comm),
                "active_partners": partner_count,
                "api_requests": request_count,
            },
            "settlements": settlements,
        }
        out = json.dumps(payload, indent=2)
        if options["output"]:
            with open(options["output"], "w", encoding="utf-8") as f:
                f.write(out)
            self.stdout.write(self.style.SUCCESS(f"Wrote {options['output']}"))
        else:
            self.stdout.write(out)
        return None
