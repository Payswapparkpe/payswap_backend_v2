"""
In-app notifications and push dispatch for ParkPe Connect chat messages.

Push dispatch is gated by ``NOTIFICATIONS_PUSH_ENABLED`` (see ``core.settings``).
When enabled and a ``DevicePushToken`` exists, we send via FCM HTTP v1 and
record a ``NotificationDeliveryLog`` row for observability.
"""
from __future__ import annotations

from django.conf import settings

from portal.models import (
    ConnectMessage,
    ConnectThread,
    DevicePushToken,
    NotificationDeliveryLog,
    NotificationMessageTemplate,
    User,
    UserNotification,
)
from portal.services.push_fcm import send_fcm_notification


def thread_muted_for_participant(thread: ConnectThread, user_id: int) -> bool:
    """True if this user has muted this thread."""
    if thread.vehicle.user_id == user_id:
        return bool(thread.owner_muted)
    if thread.scanner_user_id == user_id:
        return bool(thread.scanner_muted)
    return False


def _vehicle_reg_display(reg: str) -> str:
    return "".join(str(reg or "").strip().upper().split()) or "Vehicle"


def create_connect_message_notification(
    *,
    thread: ConnectThread,
    message: ConnectMessage,
    sender: User,
) -> None:
    """
    Create an in-app notification for the other participant. Skips if thread muted for recipient.
    Does not include phone numbers. Deep-link path matches the ParkPe SPA route for a thread.
    Optionally records push delivery intent when push is enabled and a device token exists.
    """
    if thread.vehicle.user_id == sender.pk:
        recipient = thread.scanner_user
    else:
        recipient = thread.vehicle.user
    if not recipient or recipient.pk == sender.pk:
        return
    if thread_muted_for_participant(thread, recipient.pk):
        return

    reg = _vehicle_reg_display(thread.vehicle.registration_number or "")
    preview = (message.body or "")[:200]
    if message.message_type in ("attachment", "voice"):
        preview = f"[{message.message_type}] {preview}".strip()

    title = f"Connect · {reg}"
    deep = f"/connect/chats/{thread.id}"
    meta = {
        "type": "connect_chat",
        "thread_id": thread.id,
        "message_id": message.id,
        "sender_id": sender.pk,
        "deep_link": deep,
    }
    UserNotification.objects.create(
        user=recipient,
        campaign=None,
        channel=NotificationMessageTemplate.CHANNEL_IN_APP,
        title=title[:180],
        message=preview or "New message",
        deep_link=deep[:255],
        metadata=meta,
    )
    _maybe_queue_connect_push(recipient, title=title[:160], body=preview[:200] or "New message", meta=meta)


def _maybe_queue_connect_push(*, user: User, title: str, body: str, meta: dict) -> None:
    """
    Send connect push via FCM and capture result in NotificationDeliveryLog.
    Skips when push is disabled or no token.
    """
    if not getattr(settings, "NOTIFICATIONS_PUSH_ENABLED", False):
        return
    token = DevicePushToken.objects.filter(user=user, is_active=True).order_by("-updated_at").first()
    if not token:
        return
    thread_id = meta.get("thread_id")
    message_id = meta.get("message_id")
    deep_link = str(meta.get("deep_link") or "")
    request_payload = {
        "notification": {"title": title, "body": body},
        "data": {
            "type": "connect_chat",
            "thread_id": str(thread_id),
            "message_id": str(message_id),
            "deep_link": deep_link,
        },
    }
    send_result = send_fcm_notification(
        token=token.token,
        title=title,
        body=body,
        data=request_payload["data"],
    )
    if send_result.token_invalid:
        token.is_active = False
        token.save(update_fields=["is_active", "updated_at"])

    NotificationDeliveryLog.objects.create(
        campaign=None,
        user=user,
        channel=NotificationMessageTemplate.CHANNEL_PUSH,
        status=NotificationDeliveryLog.STATUS_SENT if send_result.success else NotificationDeliveryLog.STATUS_FAILED,
        destination=token.token[:120],
        provider="connect_chat",
        request_payload=request_payload,
        response_payload=send_result.response_payload or {"provider": "fcm_v1"},
        error_message=send_result.error_message[:1500],
    )
