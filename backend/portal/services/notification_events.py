from __future__ import annotations

from typing import Optional

from portal.services.notification_orchestrator import NotificationOrchestrator
from portal.utils.logging_helper import get_logger

logger = get_logger("portal.notifications.events")


def emit_notification_event(
    event_key: str,
    *,
    actor_id: Optional[int] = None,
    payload: Optional[dict] = None,
) -> None:
    try:
        sent = NotificationOrchestrator().dispatch_event(
            event_key,
            actor_id=actor_id,
            event_payload=payload or {},
        )
        logger.info(
            "notification_event_dispatched",
            extra_data={"event_key": event_key, "sent": sent, "actor_id": actor_id},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "notification_event_dispatch_failed",
            extra_data={"event_key": event_key, "actor_id": actor_id, "error": str(exc)},
        )
