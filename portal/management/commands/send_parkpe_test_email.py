"""
Send a test email via Parkpe SMTP (voucher system) to verify configuration.
Usage: python manage.py send_parkpe_test_email sandeep@payswap.in
"""
from django.core.management.base import BaseCommand
from django.core.mail import send_mail, get_connection
from core.config import payswap_config


class Command(BaseCommand):
    help = "Send a test email via Parkpe SMTP to the given address (e.g. sandeep@payswap.in)."

    def add_arguments(self, parser):
        parser.add_argument(
            "to_email",
            type=str,
            default="sandeep@payswap.in",
            nargs="?",
            help="Recipient email address",
        )

    def handle(self, *args, **options):
        to = options["to_email"]
        if not payswap_config.is_parkpe_smtp_configured():
            self.stderr.write(
                self.style.ERROR(
                    "Parkpe SMTP is not configured. Set SMTP_HOST_Parkpe, SMTP_USER_Parkpe, "
                    "SMTP_PASSWORD_Parkpe in .env"
                )
            )
            return
        parkpe = payswap_config.get_email_config_parkpe()
        conn = get_connection(
            backend=parkpe["EMAIL_BACKEND"],
            host=parkpe["EMAIL_HOST"],
            port=parkpe["EMAIL_PORT"],
            username=parkpe["EMAIL_HOST_USER"],
            password=parkpe["EMAIL_HOST_PASSWORD"],
            use_tls=parkpe["EMAIL_USE_TLS"],
            fail_silently=False,
        )
        subject = "Payswap – Parkpe SMTP test (voucher system)"
        message = (
            "This is a test email sent via Parkpe SMTP (Zoho). "
            "If you received this, Parkpe SMTP is working for the voucher system."
        )
        try:
            n = send_mail(
                subject=subject,
                message=message,
                from_email=parkpe["DEFAULT_FROM_EMAIL"],
                recipient_list=[to],
                fail_silently=False,
                connection=conn,
            )
            self.stdout.write(
                self.style.SUCCESS(f"SUCCESS: Test email sent to {to} via Parkpe SMTP. Count={n}")
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"FAILED: {e}"))
