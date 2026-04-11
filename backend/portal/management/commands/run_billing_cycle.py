"""
Run monthly billing cycle: create settlements for previous month (if missing) and generate invoices.
Designed for cron: 0 2 1 * * (run on 1st of month at 2am).

Usage:
  python manage.py run_billing_cycle
  python manage.py run_billing_cycle --period=2025-01 --email
"""
import time
from django.core.management.base import BaseCommand
from portal.services.billing_service import run_billing_cycle


class Command(BaseCommand):
    help = "Run billing cycle: settlements + generate_invoices for a period (default: previous month)."

    def add_arguments(self, parser):
        parser.add_argument("--period", type=str, default=None, help="YYYY-MM (default: previous month).")
        parser.add_argument("--email", action="store_true", help="Email invoices to partners.")
        parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation (HTML only).")

    def handle(self, *args, **options):
        start = time.time()
        try:
            result = run_billing_cycle(
                period=options.get("period"),
                email=options.get("email", False),
                pdf=not options.get("no_pdf", False),
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Billing cycle {result['period']}: {result['partners_processed']} partners, "
                    f"{result['documents_generated']} documents, {result['errors']} errors."
                )
            )
        except Exception as e:
            raise
