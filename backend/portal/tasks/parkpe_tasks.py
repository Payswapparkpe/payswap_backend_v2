from celery import shared_task
from django.utils import timezone

from portal.utils.logging_helper import get_logger

logger = get_logger("portal.tasks.parkpe")


@shared_task(name="portal.tasks.reconcile_pending_parkpe_orders", bind=True)
def reconcile_pending_parkpe_orders_task(self):
    """Periodic reconciliation for pending ParkPe payment orders."""
    from api.parkpe_api.views import reconcile_pending_cashfree_orders

    result = reconcile_pending_cashfree_orders(limit=300, min_age_minutes=2, max_age_hours=48)
    logger.info("parkpe_pending_reconcile_run", extra_data=result)
    return result


@shared_task(name="portal.tasks.send_challan_payment_notification")
def send_challan_payment_notification_task(user_id: int, challan_number: str, amount: str, transaction_id: str):
    """Create in-app notification entry for successful challan payment."""
    from portal.models import User, UserNotification

    user = User.objects.filter(id=user_id).first()
    if not user:
        return {"success": False, "error": "user_not_found"}
    title = "Challan paid successfully"
    message = f"Challan {challan_number} paid for INR {amount}. Ref: {transaction_id}"
    row = UserNotification.objects.create(
        user=user,
        title=title,
        message=message,
        channel=UserNotification.CHANNEL_IN_APP,
        metadata={
            "service": "challan",
            "challanNumber": challan_number,
            "transactionId": transaction_id,
            "amount": amount,
            "paidAt": timezone.now().isoformat(),
        },
        deep_link="/challan/history",
    )
    return {"success": True, "id": row.id}


@shared_task(name="portal.tasks.scan_saved_vehicles_for_challans")
def scan_saved_vehicles_for_challans_task(limit: int = 100):
    """
    Periodic scan: refresh challans for saved vehicles and notify on new pending challans.
    """
    from api.parkpe_api.views import _instantpay_challan_lookup, _upsert_cached_challans, _normalize_challan_status
    from portal.models import ParkPeSavedVehicle, UserNotification

    scanned = 0
    notified = 0
    rows = (
        ParkPeSavedVehicle.objects.filter(is_active=True)
        .select_related("user")
        .order_by("last_checked_at", "updated_at")[: max(1, min(int(limit or 100), 500))]
    )
    for row in rows:
        user = row.user
        req = type(
            "ChallanCronRequest",
            (),
            {
                "request_id": f"cron_{timezone.now().strftime('%Y%m%d%H%M%S')}_{row.id}",
                "user": user,
            },
        )()
        result, challans, _ = _instantpay_challan_lookup(
            request=req,
            vehicle_number=row.registration_number,
            state="",
        )
        scanned += 1
        if not result.get("success"):
            row.last_checked_at = timezone.now()
            row.save(update_fields=["last_checked_at", "updated_at"])
            continue
        _upsert_cached_challans(user, row.registration_number, challans)
        pending_count = sum(1 for c in challans if _normalize_challan_status(c.get("status")) == "pending")
        if pending_count > row.last_known_pending_count:
            UserNotification.objects.create(
                user=user,
                title="New challan detected",
                message=f"{pending_count} pending challan(s) found for {row.registration_number}.",
                channel=UserNotification.CHANNEL_IN_APP,
                metadata={
                    "service": "challan",
                    "registrationNumber": row.registration_number,
                    "pendingCount": pending_count,
                },
                deep_link=f"/challan?vehicleNumber={row.registration_number}",
            )
            notified += 1
        row.last_known_pending_count = pending_count
        row.last_checked_at = timezone.now()
        row.save(update_fields=["last_known_pending_count", "last_checked_at", "updated_at"])
    logger.info("challan_saved_vehicle_scan", extra_data={"scanned": scanned, "notified": notified})
    return {"success": True, "scanned": scanned, "notified": notified}
