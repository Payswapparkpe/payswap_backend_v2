"""
Celery: reconcile stale parking transactions (e.g. FASTag issuer timeout mid-flight).
"""
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from portal.models import ParkingTransaction
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.tasks.parking_reconcile")


@shared_task
def reconcile_pending_parking_transactions():
    """
    Fail-safe for orphaned PENDING rows (crash between issuer call and DB finalize).
    Production should replace this with issuer status polling + retry policy.
    """
    cutoff = timezone.now() - timedelta(minutes=15)
    qs = ParkingTransaction.objects.filter(
        status=ParkingTransaction.STATUS_PENDING,
        payment_method=ParkingTransaction.METHOD_FASTAG,
        created_at__lt=cutoff,
    )
    count = 0
    for tx in qs.iterator():
        tx.status = ParkingTransaction.STATUS_FAILED
        tx.failure_reason = "reconcile_timeout"
        tx.save(update_fields=["status", "failure_reason", "updated_at"])
        count += 1
    if count:
        logger.warning("parking_fastag_tx_reconciled", extra_data={"failed_count": count})
    return {"marked_failed": count}
