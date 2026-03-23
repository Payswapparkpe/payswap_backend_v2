from celery import shared_task

from portal.utils.logging_helper import get_logger

logger = get_logger("portal.tasks.parkpe")


@shared_task(name="portal.tasks.reconcile_pending_parkpe_orders", bind=True)
def reconcile_pending_parkpe_orders_task(self):
    """Periodic reconciliation for pending ParkPe payment orders."""
    from api.parkpe_api.views import reconcile_pending_cashfree_orders

    result = reconcile_pending_cashfree_orders(limit=300, min_age_minutes=2, max_age_hours=48)
    logger.info("parkpe_pending_reconcile_run", extra_data=result)
    return result
