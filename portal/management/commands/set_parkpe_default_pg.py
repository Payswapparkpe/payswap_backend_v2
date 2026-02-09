"""
Ensure ParkPe has Cashfree as the voucher-purchase gateway and set it as default.
Run: python manage.py set_parkpe_default_pg
"""
from django.core.management.base import BaseCommand
from portal.models import ParkPePaymentGatewayConfig


class Command(BaseCommand):
    help = "Ensure ParkPe voucher purchase has Cashfree config and set as default."

    def handle(self, *args, **options):
        config, created = ParkPePaymentGatewayConfig.objects.get_or_create(
            gateway=ParkPePaymentGatewayConfig.CASHFREE,
            service_code="",
            defaults={
                "enabled": True,
                "is_default_for_voucher_purchase": True,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Created Cashfree config for voucher purchase."))
        else:
            if not config.is_default_for_voucher_purchase:
                config.is_default_for_voucher_purchase = True
                config.save(update_fields=["is_default_for_voucher_purchase", "updated_at"])
                self.stdout.write(self.style.SUCCESS("Set Cashfree as default for voucher purchase."))
            else:
                self.stdout.write("Config exists: Cashfree (voucher purchase, default).")

        # Unset default from any other gateway (e.g. old Razorpay config)
        ParkPePaymentGatewayConfig.objects.filter(
            service_code="",
        ).exclude(gateway=ParkPePaymentGatewayConfig.CASHFREE).update(is_default_for_voucher_purchase=False)
        self.stdout.write(self.style.SUCCESS("Done. ParkPe voucher purchase uses Cashfree PG only."))
