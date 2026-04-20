"""
Backfill BillingDocument rows for historical ParkPe ledger / PG orders (idempotent).

Uses the same tax snapshot rules as live emitters. Safe to re-run: existing
idempotency keys are left unchanged.
"""
from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand
from portal.models import BillingDocument, ParkPePaymentOrder, ParkPeVoucherTransaction
from portal.services.billing_document_service import (
    idempotency_key_for_parkpe_voucher_transaction,
    idempotency_key_for_voucher_purchase_order,
    record_billing_from_parkpe_voucher_transaction,
    record_voucher_purchase_billing,
)


def _parse_date(value: str | None):
    if not value or not str(value).strip():
        return None
    return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()


class Command(BaseCommand):
    help = (
        "Create missing BillingDocument rows for past ParkPeVoucherTransaction and "
        "completed ParkPePaymentOrder (voucher purchase). Use --dry-run to preview counts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write; report how many rows would get a new BillingDocument.",
        )
        parser.add_argument(
            "--voucher-txns-only",
            action="store_true",
            help="Only process ParkPeVoucherTransaction.",
        )
        parser.add_argument(
            "--orders-only",
            action="store_true",
            help="Only process completed ParkPePaymentOrder (voucher top-up).",
        )
        parser.add_argument(
            "--since",
            type=str,
            default="",
            help="Inclusive lower bound on created_at date (YYYY-MM-DD).",
        )
        parser.add_argument(
            "--until",
            type=str,
            default="",
            help="Inclusive upper bound on created_at date (YYYY-MM-DD).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Max rows per source (0 = no limit). For large DBs, run in chunks.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        voucher_only: bool = options["voucher_txns_only"]
        orders_only: bool = options["orders_only"]
        since = _parse_date(options.get("since") or "")
        until = _parse_date(options.get("until") or "")
        limit: int = max(0, int(options.get("limit") or 0))

        if voucher_only and orders_only:
            self.stderr.write(self.style.ERROR("Use at most one of --voucher-txns-only / --orders-only."))
            return

        process_vouchers = not orders_only
        process_orders = not voucher_only

        stats = {
            "voucher_txns_scanned": 0,
            "voucher_txns_missing_doc": 0,
            "voucher_txns_created": 0,
            "voucher_txns_errors": 0,
            "orders_scanned": 0,
            "orders_missing_doc": 0,
            "orders_created": 0,
            "orders_errors": 0,
        }

        def _apply_date(qs, field: str):
            if since:
                qs = qs.filter(**{f"{field}__date__gte": since})
            if until:
                qs = qs.filter(**{f"{field}__date__lte": until})
            return qs

        if process_vouchers:
            qs = ParkPeVoucherTransaction.objects.filter(user_id__isnull=False).order_by("pk")
            qs = _apply_date(qs, "created_at")
            if limit:
                qs = qs[:limit]
            for txn in qs.iterator(chunk_size=500):
                stats["voucher_txns_scanned"] += 1
                key = idempotency_key_for_parkpe_voucher_transaction(txn)
                if not key:
                    continue
                missing = not BillingDocument.objects.filter(idempotency_key=key).exists()
                if missing:
                    stats["voucher_txns_missing_doc"] += 1
                if dry_run:
                    continue
                try:
                    record_billing_from_parkpe_voucher_transaction(txn)
                    if missing:
                        stats["voucher_txns_created"] += 1
                except Exception as exc:
                    stats["voucher_txns_errors"] += 1
                    self.stderr.write(self.style.WARNING(f"Voucher txn pk={txn.pk}: {exc}"))

        if process_orders:
            qs = ParkPePaymentOrder.objects.filter(status=ParkPePaymentOrder.COMPLETED).order_by("pk")
            qs = _apply_date(qs, "created_at")
            if limit:
                qs = qs[:limit]
            for order in qs.iterator(chunk_size=500):
                stats["orders_scanned"] += 1
                key = idempotency_key_for_voucher_purchase_order(order.order_id)
                missing = not BillingDocument.objects.filter(idempotency_key=key).exists()
                if missing:
                    stats["orders_missing_doc"] += 1
                if dry_run:
                    continue
                try:
                    record_voucher_purchase_billing(
                        user=order.user,
                        order_id=order.order_id,
                        amount=order.amount,
                    )
                    if missing:
                        stats["orders_created"] += 1
                except Exception as exc:
                    stats["orders_errors"] += 1
                    self.stderr.write(self.style.WARNING(f"Order {order.order_id}: {exc}"))

        mode = "DRY RUN — " if dry_run else ""
        self.stdout.write(self.style.NOTICE(f"{mode}Backfill billing documents"))
        self.stdout.write(f"  ParkPeVoucherTransaction: scanned={stats['voucher_txns_scanned']}")
        if dry_run:
            self.stdout.write(f"    would create (missing idempotency row)={stats['voucher_txns_missing_doc']}")
        else:
            self.stdout.write(
                f"    new docs created={stats['voucher_txns_created']} errors={stats['voucher_txns_errors']}"
            )
        self.stdout.write(f"  ParkPePaymentOrder (completed): scanned={stats['orders_scanned']}")
        if dry_run:
            self.stdout.write(f"    would create (missing idempotency row)={stats['orders_missing_doc']}")
        else:
            self.stdout.write(
                f"    new docs created={stats['orders_created']} errors={stats['orders_errors']}"
            )
