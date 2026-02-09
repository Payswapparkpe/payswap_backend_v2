"""
Seed APIProduct rows for Parkpe and Payswap.
Creates product-level toggles: Mobikwik BBPS, Euronet BBPS (and any others) per platform.
"""
from django.core.management.base import BaseCommand

from api_management.models import APIProduct


# (product_slug, display_name, display_order)
DEFAULT_PRODUCTS = [
    ("mobikwik_bbps", "Mobikwik BBPS", 10),
    ("euronet_bbps", "Euronet BBPS", 20),
]


class Command(BaseCommand):
    help = "Seed APIProduct for Parkpe and Payswap (Mobikwik BBPS, Euronet BBPS, etc.)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only print what would be created.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        created = 0
        for platform in (APIProduct.PLATFORM_PARKPE, APIProduct.PLATFORM_PAYSWAP):
            for product_slug, name, order in DEFAULT_PRODUCTS:
                if dry_run:
                    self.stdout.write(f"Would create/update: {platform} / {product_slug} ({name})")
                    created += 1
                    continue
                obj, created_this = APIProduct.objects.update_or_create(
                    platform=platform,
                    product_slug=product_slug,
                    defaults={"name": name, "display_order": order, "enabled": True},
                )
                if created_this:
                    created += 1
                    self.stdout.write(f"Created: {obj}")
        self.stdout.write(self.style.SUCCESS(f"Seed complete. Created: {created}"))
