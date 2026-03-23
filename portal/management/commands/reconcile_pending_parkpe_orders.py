from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Recheck pending ParkPe Cashfree orders and update status (completed/failed)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=200,
            help="Max pending orders to check per run (default: 200).",
        )
        parser.add_argument(
            "--min-age-minutes",
            type=int,
            default=2,
            help="Skip very new pending orders (default: 2 minutes).",
        )
        parser.add_argument(
            "--max-age-hours",
            type=int,
            default=48,
            help="Only check orders created within this many hours (default: 48).",
        )
        parser.add_argument(
            "--order-id",
            action="append",
            default=[],
            help="Specific order ID to recheck (repeatable).",
        )

    def handle(self, *args, **options):
        from api.parkpe_api.views import reconcile_pending_cashfree_orders

        result = reconcile_pending_cashfree_orders(
            limit=options["limit"],
            min_age_minutes=options["min_age_minutes"],
            max_age_hours=options["max_age_hours"],
            order_ids=options.get("order_id") or None,
        )
        self.stdout.write(
            self.style.SUCCESS(
                "pending_reconcile checked={checked} completed={completed} failed={failed} "
                "still_pending={still_pending} errors={errors}".format(**result)
            )
        )
