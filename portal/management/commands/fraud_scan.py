"""
Fraud detection scan: high velocity, pattern abuse, repeated failures, balance gaming.
Flags suspicious activity; does not auto-block. Run via cron or manually.

Usage:
  python manage.py fraud_scan
  python manage.py fraud_scan --window=24 --dry-run
"""
import logging
import time
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, Sum

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Scan for fraud indicators: high velocity, repeated failures, balance gaming."

    def add_arguments(self, parser):
        parser.add_argument(
            "--window",
            type=int,
            default=24,
            help="Time window in hours (default 24).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report, do not write flags.",
        )
        parser.add_argument(
            "--velocity-threshold",
            type=int,
            default=1000,
            help="Max requests per hour per api_key to flag (default 1000).",
        )
        parser.add_argument(
            "--failure-threshold",
            type=int,
            default=50,
            help="Min consecutive/ratio failures to flag (default 50).",
        )

    def handle(self, *args, **options):
        return self._handle_impl(*args, **options)

    def _handle_impl(self, *args, **options):
        from portal.models import APIKeyUsageLog, ResellerPartner

        window_h = options["window"]
        dry_run = options["dry_run"]
        velocity_threshold = options["velocity_threshold"]
        failure_threshold = options["failure_threshold"]

        since = timezone.now() - timedelta(hours=window_h)
        self.stdout.write(f"Fraud scan: last {window_h}h (dry_run={dry_run})")

        flags = []

        # High velocity: requests per api_key
        key_counts = (
            APIKeyUsageLog.objects.filter(created_at__gte=since, api_key_id__isnull=False)
            .values("api_key_id")
            .annotate(c=Count("id"))
            .filter(c__gte=velocity_threshold)
        )
        for row in key_counts:
            flags.append(
                {"type": "high_velocity", "api_key_id": row["api_key_id"], "requests": row["c"], "window_h": window_h}
            )
            self.stdout.write(self.style.WARNING(f"  High velocity: api_key_id={row['api_key_id']} requests={row['c']}"))

        # Repeated failures: api_keys with many 4xx/5xx in window
        failed = (
            APIKeyUsageLog.objects.filter(created_at__gte=since, status_code__gte=400)
            .values("api_key_id")
            .annotate(c=Count("id"))
            .filter(c__gte=failure_threshold)
        )
        for row in failed:
            if row["api_key_id"]:
                flags.append(
                    {"type": "repeated_failures", "api_key_id": row["api_key_id"], "failures": row["c"], "window_h": window_h}
                )
                self.stdout.write(self.style.WARNING(f"  Repeated failures: api_key_id={row['api_key_id']} failures={row['c']}"))

        # Balance gaming: partner with negative or zero wallet but high recent revenue (simplified)
        partners_with_wallet = ResellerPartner.objects.filter(
            status="ACTIVE", wallet_id__isnull=False
        ).select_related("wallet")
        for partner in partners_with_wallet:
            try:
                bal = partner.wallet.balance
                if bal is not None and float(bal) < 0:
                    flags.append(
                        {"type": "negative_balance", "partner_id": partner.id, "partner_code": partner.partner_code, "balance": str(bal)}
                    )
                    self.stdout.write(self.style.WARNING(f"  Negative balance: {partner.partner_code} balance={bal}"))
            except Exception as e:
                logger.debug("Wallet check for %s: %s", partner.partner_code, e)

        # Persist flags (optional: store in a FraudFlag model or log)
        if not dry_run and flags:
            for f in flags:
                logger.warning("fraud_scan_flag: %s", f)

        self.stdout.write(self.style.SUCCESS(f"Scan complete: {len(flags)} flag(s)."))
