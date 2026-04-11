"""
Generate GST Invoice, Settlement Statement, Commission Invoice per partner for a billing period.
Stores HTML (and PDF if xhtml2pdf is installed) under PARTNER_INVOICES_DIR.
Cron: run monthly after run_billing_cycle (or use run_billing_cycle which creates settlements + generates).

Usage:
  python manage.py generate_invoices
  python manage.py generate_invoices --period=2025-01
  python manage.py generate_invoices --period=2025-01 --partner=1
  python manage.py generate_invoices --email --pdf
"""
import time
from django.core.management.base import BaseCommand

from portal.models import ResellerPartner
from portal.services.billing_service import run_billing_cycle, generate_partner_documents


class Command(BaseCommand):
    help = "Generate partner invoices (GST, Settlement, Commission) for a billing period."

    def add_arguments(self, parser):
        parser.add_argument(
            "--period",
            type=str,
            default=None,
            help="Billing period YYYY-MM (default: previous month).",
        )
        parser.add_argument(
            "--partner",
            type=int,
            default=None,
            help="Partner ID (optional; default: all active partners).",
        )
        parser.add_argument("--email", action="store_true", help="Email invoices to partner contact.")
        parser.add_argument("--pdf", action="store_true", default=True, help="Generate PDF when possible (default True).")
        parser.add_argument("--no-pdf", action="store_false", dest="pdf", help="Only generate HTML.")

    def handle(self, *args, **options):
        return self._handle_impl(*args, **options)

    def _handle_impl(self, *args, **options):
        period = options.get("period")
        partner_id = options.get("partner")
        email = options.get("email", False)
        pdf = options.get("pdf", True)

        if partner_id:
            try:
                partner = ResellerPartner.objects.get(id=partner_id, status="ACTIVE")
            except ResellerPartner.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Partner id={partner_id} not found or not ACTIVE."))
                return
            files = generate_partner_documents(partner, period or self._default_period(), send_email=email, pdf=pdf)
            self.stdout.write(self.style.SUCCESS(f"Generated {len(files)} file(s) for {partner.company_name}."))
            for doc_type, path in files:
                self.stdout.write(f"  {doc_type}: {path}")
            return

        result = run_billing_cycle(period=period, email=email, pdf=pdf)
        self.stdout.write(
            self.style.SUCCESS(
                f"Billing cycle {result['period']}: {result['partners_processed']} partners, "
                f"{result['documents_generated']} documents, {result['errors']} errors."
            )
        )

    def _default_period(self):
        from datetime import timedelta
        from django.utils import timezone
        prev = timezone.now().replace(day=1) - timedelta(days=1)
        return prev.strftime("%Y-%m")
