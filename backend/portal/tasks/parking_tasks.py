"""
Celery tasks for Parkpe Smart Parking Platform.

Tasks:
- send_booking_notifications_task: async WhatsApp + Email after booking
- auto_expire_unclaimed_bookings: cancel confirmed bookings not entered within grace period
- send_booking_reminders: WhatsApp reminder 1 hour before booking start
- rollup_daily_revenue: nightly revenue aggregation for all locations
- send_monthly_revenue_report: email monthly PDF summary to parking owners
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from portal.utils.logging_helper import get_logger

logger = get_logger("portal.tasks.parking")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_notifications_task(self, booking_pk: str):
    """
    Send WhatsApp + Email ticket after booking creation.
    Runs async so booking API response is instant.
    """
    try:
        from portal.models import ParkingBooking
        from portal.services.parking_service import _ensure_ticket
        from portal.services.parking_notification_service import (
            send_booking_confirmation_whatsapp,
            send_booking_confirmation_email,
        )

        booking = ParkingBooking.objects.select_related(
            "slot__zone__location", "customer"
        ).get(pk=booking_pk)

        ticket = _ensure_ticket(booking)
        wa_sent = send_booking_confirmation_whatsapp(booking, ticket)
        email_sent = send_booking_confirmation_email(booking, ticket)

        logger.info(
            "parking_booking_notifications_sent",
            extra_data={
                "booking_ref": booking.booking_reference,
                "whatsapp": wa_sent,
                "email": email_sent,
            },
        )
    except Exception as exc:
        logger.warning(
            "parking_booking_notifications_failed",
            extra_data={"booking_pk": str(booking_pk), "error": str(exc)},
        )
        raise self.retry(exc=exc)


@shared_task
def auto_expire_unclaimed_bookings():
    """
    Cancel CONFIRMED bookings where customer never arrived within grace period.
    Runs every 5 minutes via Celery Beat.
    """
    from portal.models import ParkingBooking, ParkingSlot
    from django.db.models import F

    grace = timezone.now() - timedelta(minutes=15)
    expired_bookings = ParkingBooking.objects.filter(
        status=ParkingBooking.STATUS_CONFIRMED,
        from_dt__lt=grace,
        actual_entry_time__isnull=True,
    )

    count = 0
    for booking in expired_bookings.select_related("slot"):
        booking.status = ParkingBooking.STATUS_EXPIRED
        booking.cancellation_reason = "Auto-expired: customer did not arrive within 15 minutes."
        booking.save(update_fields=["status", "cancellation_reason", "updated_at"])

        ParkingSlot.objects.filter(pk=booking.slot_id).update(
            status=ParkingSlot.STATUS_AVAILABLE,
            updated_at=timezone.now(),
        )
        count += 1

    if count:
        logger.info(
            "parking_auto_expired",
            extra_data={"count": count},
        )
    return count


@shared_task
def send_booking_reminders():
    """
    Send WhatsApp reminder to customers whose booking starts in ~60 minutes.
    Runs every 15 minutes via Celery Beat.
    """
    from portal.models import ParkingBooking
    from portal.services.parking_notification_service import send_reminder_whatsapp

    now = timezone.now()
    reminder_window_start = now + timedelta(minutes=55)
    reminder_window_end = now + timedelta(minutes=65)

    bookings = ParkingBooking.objects.filter(
        status=ParkingBooking.STATUS_CONFIRMED,
        from_dt__range=(reminder_window_start, reminder_window_end),
    ).select_related("slot__zone__location")

    count = 0
    for booking in bookings:
        try:
            send_reminder_whatsapp(booking, minutes_before=60)
            count += 1
        except Exception as e:
            logger.warning(
                "parking_reminder_task_failed",
                extra_data={"booking_ref": booking.booking_reference, "error": str(e)},
            )

    return count


@shared_task
def rollup_daily_revenue(date_str: str = None):
    """
    Nightly task: recalculate daily revenue records from completed bookings.
    date_str: YYYY-MM-DD, defaults to yesterday.
    """
    from portal.models import ParkingBooking, ParkingRevenue, ParkingLocation
    from django.db.models import Sum, Count
    from datetime import date

    if date_str:
        target_date = date.fromisoformat(date_str)
    else:
        target_date = (timezone.now() - timedelta(days=1)).date()

    completed_bookings = ParkingBooking.objects.filter(
        status=ParkingBooking.STATUS_COMPLETED,
        actual_exit_time__date=target_date,
    ).values("slot__zone__location_id").annotate(
        total=Count("pk"),
        revenue=Sum("final_amount"),
    )

    from decimal import Decimal
    DEFAULT_COMMISSION_PCT = Decimal("5.00")

    for row in completed_bookings:
        loc_id = row["slot__zone__location_id"]
        gross = row["revenue"] or Decimal("0")
        commission = (gross * DEFAULT_COMMISSION_PCT / Decimal("100")).quantize(Decimal("0.01"))
        net = gross - commission

        ParkingRevenue.objects.update_or_create(
            location_id=loc_id,
            date=target_date,
            defaults={
                "gross_revenue": gross,
                "commission_pct": DEFAULT_COMMISSION_PCT,
                "commission_amount": commission,
                "net_owner_amount": net,
                "total_bookings": row["total"],
            },
        )

    logger.info(
        "parking_revenue_rollup_complete",
        extra_data={"date": str(target_date), "locations": len(list(completed_bookings))},
    )


@shared_task
def send_monthly_revenue_report(year: int = None, month: int = None):
    """
    Email monthly revenue PDF report to all active parking owners.
    Runs on 1st of each month via Celery Beat.
    """
    from portal.models import ParkingOperator, EmailQueue
    from portal.services.parking_service import get_owner_revenue_summary
    from django.utils import timezone

    now = timezone.now()
    if not year:
        year = (now.replace(day=1) - timedelta(days=1)).year
    if not month:
        month = (now.replace(day=1) - timedelta(days=1)).month

    owners = ParkingOperator.objects.filter(
        role=ParkingOperator.ROLE_OWNER, is_active=True
    ).select_related("user", "location")

    for op in owners:
        try:
            summary = get_owner_revenue_summary(op.location_id, days=30)
            profile = getattr(op.user, "profile", None)
            email = getattr(profile, "email", None) or op.user.email or ""
            if not email:
                continue

            body = (
                f"Dear {getattr(profile, 'full_name', op.user.username)},\n\n"
                f"Monthly Parking Revenue Summary — {year}/{month:02d}\n"
                f"Location: {op.location.name}\n\n"
                f"Total Bookings: {summary['total_bookings']}\n"
                f"Gross Revenue: ₹{summary['total_gross_revenue']:.2f}\n"
                f"Parkpe Commission: ₹{summary['total_commission']:.2f}\n"
                f"Your Net Revenue: ₹{summary['total_net_revenue']:.2f}\n\n"
                f"Login to Hub for detailed breakdown.\n"
                f"– Parkpe Team"
            )

            EmailQueue.objects.create(
                to_email=email,
                subject=f"Parkpe Parking Monthly Report — {year}/{month:02d} — {op.location.name}",
                body=body,
                metadata={"type": "parking_monthly_report", "location_id": op.location_id},
            )
        except Exception as e:
            logger.warning(
                "parking_monthly_report_failed",
                extra_data={"operator_id": op.pk, "error": str(e)},
            )


# ─── Celery Beat schedule entries (add to settings.CELERY_BEAT_SCHEDULE) ─────
# Example:
# "parking-auto-expire": {"task": "portal.tasks.parking_tasks.auto_expire_unclaimed_bookings", "schedule": 300},
# "parking-reminders": {"task": "portal.tasks.parking_tasks.send_booking_reminders", "schedule": 900},
# "parking-daily-rollup": {"task": "portal.tasks.parking_tasks.rollup_daily_revenue", "schedule": crontab(hour=1, minute=0)},
# "parking-monthly-report": {"task": "portal.tasks.parking_tasks.send_monthly_revenue_report", "schedule": crontab(day_of_month=1, hour=8, minute=0)},
