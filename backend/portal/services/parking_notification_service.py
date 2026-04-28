"""
Parking Notification Service
Handles WhatsApp and Email delivery of parking tickets.
Uses existing NotificationServiceV2 infrastructure.
"""
import io
import json
import qrcode
from typing import Optional

from django.conf import settings
from django.utils import timezone

from portal.models import ParkingBooking, ParkingTicket
from portal.services.notification_service_v2 import NotificationServiceV2
from portal.utils.logging_helper import get_logger
from portal.utils.phone_utils import normalize_phone_number

logger = get_logger("portal.services.parking_notification")

_notification_svc = None


def _get_notification_service() -> NotificationServiceV2:
    global _notification_svc
    if _notification_svc is None:
        _notification_svc = NotificationServiceV2()
    return _notification_svc


# ─── QR Code generation ───────────────────────────────────────────────────────

def generate_qr_bytes(qr_data: str) -> bytes:
    """Generate QR code PNG bytes for a given data string."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ─── WhatsApp ticket delivery ─────────────────────────────────────────────────

def send_booking_confirmation_whatsapp(booking: ParkingBooking, ticket: ParkingTicket) -> bool:
    """
    Send booking confirmation + QR code to customer WhatsApp.
    Message format follows WhatsApp Business API template.
    """
    phone = booking.customer_phone or ""
    if not phone:
        logger.warning(
            "parking_whatsapp_skip_no_phone",
            extra_data={"booking_ref": booking.booking_reference},
        )
        return False

    try:
        phone = normalize_phone_number(phone)
    except Exception:
        pass

    location = booking.slot.zone.location
    from_local = booking.from_dt.astimezone().strftime("%d %b %Y, %I:%M %p")
    to_local = booking.to_dt.astimezone().strftime("%d %b %Y, %I:%M %p")

    message = (
        f"*Parkpe Parking Ticket*\n\n"
        f"Booking: *{booking.booking_reference}*\n"
        f"Location: {location.name}\n"
        f"Address: {location.address}, {location.city}\n"
        f"Slot: {booking.slot.slot_code} ({booking.vehicle_type.replace('_', ' ').title()})\n"
        f"Vehicle: {booking.vehicle_number}\n"
        f"From: {from_local}\n"
        f"To: {to_local}\n"
        f"Amount: ₹{booking.estimated_amount}\n\n"
        f"Ticket No: {ticket.ticket_number}\n\n"
        f"Show QR at entry. Have a safe parking experience!\n"
        f"– Parkpe Team"
    )

    try:
        svc = _get_notification_service()
        result = svc.send_whatsapp(
            phone_number=phone,
            message=message,
            metadata={
                "type": "parking_ticket",
                "booking_ref": booking.booking_reference,
                "ticket_no": ticket.ticket_number,
            },
        )
        if result:
            ParkingTicket.objects.filter(pk=ticket.pk).update(
                whatsapp_sent_at=timezone.now(),
                whatsapp_phone=phone,
            )
            logger.info(
                "parking_whatsapp_sent",
                extra_data={"booking_ref": booking.booking_reference, "phone": phone[-4:]},
            )
            return True
    except Exception as e:
        logger.warning(
            "parking_whatsapp_failed",
            extra_data={"booking_ref": booking.booking_reference, "error": str(e)},
        )
    return False


def send_booking_confirmation_email(booking: ParkingBooking, ticket: ParkingTicket) -> bool:
    """
    Send booking confirmation email with ticket details.
    Uses existing EmailQueue infrastructure.
    """
    email = booking.customer_email or ""
    if not email:
        logger.warning(
            "parking_email_skip_no_email",
            extra_data={"booking_ref": booking.booking_reference},
        )
        return False

    location = booking.slot.zone.location
    from_local = booking.from_dt.astimezone().strftime("%d %b %Y, %I:%M %p")
    to_local = booking.to_dt.astimezone().strftime("%d %b %Y, %I:%M %p")

    subject = f"Parkpe Parking Ticket — {booking.booking_reference}"
    body = f"""
Dear {booking.customer_name or "Customer"},

Your parking has been confirmed!

Booking Reference: {booking.booking_reference}
Ticket Number: {ticket.ticket_number}

Location: {location.name}
Address: {location.address}, {location.city}
Slot: {booking.slot.slot_code}
Vehicle: {booking.vehicle_number} ({booking.vehicle_type.replace('_', ' ').title()})
From: {from_local}
To: {to_local}
Estimated Amount: ₹{booking.estimated_amount}

Show your QR code at the parking entry gate.

Thank you for using Parkpe!
Team Parkpe
    """.strip()

    try:
        from portal.models import EmailQueue
        EmailQueue.objects.create(
            to_email=email,
            subject=subject,
            body=body,
            metadata={
                "type": "parking_ticket",
                "booking_ref": booking.booking_reference,
            },
        )
        ParkingTicket.objects.filter(pk=ticket.pk).update(
            email_sent_at=timezone.now(),
            email_address=email,
        )
        logger.info(
            "parking_email_queued",
            extra_data={"booking_ref": booking.booking_reference},
        )
        return True
    except Exception as e:
        logger.warning(
            "parking_email_failed",
            extra_data={"booking_ref": booking.booking_reference, "error": str(e)},
        )
    return False


def send_exit_receipt_whatsapp(booking: ParkingBooking) -> bool:
    """Send exit receipt with final charge to customer WhatsApp."""
    phone = booking.customer_phone or ""
    if not phone:
        return False
    try:
        phone = normalize_phone_number(phone)
    except Exception:
        pass

    entry = booking.actual_entry_time
    exit_t = booking.actual_exit_time or timezone.now()
    duration_min = int((exit_t - entry).total_seconds() / 60) if entry else 0
    hours = duration_min // 60
    minutes = duration_min % 60

    message = (
        f"*Parkpe Parking Receipt*\n\n"
        f"Booking: *{booking.booking_reference}*\n"
        f"Vehicle: {booking.vehicle_number}\n"
        f"Entry: {entry.astimezone().strftime('%d %b, %I:%M %p') if entry else 'N/A'}\n"
        f"Exit: {exit_t.astimezone().strftime('%d %b, %I:%M %p')}\n"
        f"Duration: {hours}h {minutes}m\n"
        f"Amount Charged: *₹{booking.final_amount or booking.estimated_amount}*\n\n"
        f"Thank you for parking with Parkpe!"
    )

    try:
        svc = _get_notification_service()
        svc.send_whatsapp(
            phone_number=phone,
            message=message,
            metadata={"type": "parking_receipt", "booking_ref": booking.booking_reference},
        )
        logger.info("parking_receipt_whatsapp_sent", extra_data={"booking_ref": booking.booking_reference})
        return True
    except Exception as e:
        logger.warning("parking_receipt_whatsapp_failed", extra_data={"error": str(e)})
    return False


def send_reminder_whatsapp(booking: ParkingBooking, minutes_before: int = 60) -> bool:
    """Send a reminder that booking starts soon."""
    phone = booking.customer_phone or ""
    if not phone:
        return False
    try:
        phone = normalize_phone_number(phone)
    except Exception:
        pass

    location = booking.slot.zone.location
    start = booking.from_dt.astimezone().strftime("%I:%M %p")

    message = (
        f"*Parkpe Reminder* ⏰\n\n"
        f"Your parking at *{location.name}* starts in {minutes_before} minutes.\n"
        f"Slot: {booking.slot.slot_code} | Time: {start}\n"
        f"Booking Ref: {booking.booking_reference}\n\n"
        f"Please arrive on time to avoid slot release."
    )

    try:
        svc = _get_notification_service()
        svc.send_whatsapp(
            phone_number=phone,
            message=message,
            metadata={"type": "parking_reminder", "booking_ref": booking.booking_reference},
        )
        return True
    except Exception as e:
        logger.warning("parking_reminder_failed", extra_data={"error": str(e)})
    return False


# ─── Resend ticket ────────────────────────────────────────────────────────────

def resend_ticket(booking_reference: str) -> dict:
    """Resend WhatsApp + Email for a confirmed booking."""
    try:
        booking = ParkingBooking.objects.select_related(
            "slot__zone__location", "customer", "ticket"
        ).get(booking_reference=booking_reference)
    except ParkingBooking.DoesNotExist:
        raise ValueError("Booking not found.")

    try:
        ticket = booking.ticket
    except ParkingTicket.DoesNotExist:
        from portal.services.parking_service import _ensure_ticket
        ticket = _ensure_ticket(booking)

    ParkingTicket.objects.filter(pk=ticket.pk).update(resend_count=ticket.resend_count + 1)

    wa_sent = send_booking_confirmation_whatsapp(booking, ticket)
    email_sent = send_booking_confirmation_email(booking, ticket)

    return {
        "booking_reference": booking_reference,
        "whatsapp_sent": wa_sent,
        "email_sent": email_sent,
    }
