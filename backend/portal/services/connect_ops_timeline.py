"""
Merged Connect activity feed for ops (scan, onboard, call, chat) — one chronological stream.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone

from portal.models import (
    ConnectCallLog,
    ConnectMessage,
    ConnectQrOnboardLog,
    ConnectScanLog,
    VehicleQRCode,
)


def fetch_connect_timeline(
    *,
    qr_code: str | None = None,
    user_id: int | None = None,
    hours: int = 168,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """
    Return recent events newest-first. Pass exactly one of qr_code or user_id.

    Each item: at (datetime), kind, title, detail, ref_id (optional).
    """
    has_qr = bool((qr_code or "").strip())
    has_u = user_id is not None
    if has_qr == has_u:
        return []

    now = timezone.now()
    since = now - timedelta(hours=max(1, min(hours, 720)))
    events: list[dict[str, Any]] = []

    if qr_code:
        qc = (qr_code or "").strip()[:128]
        vehicle_id = (
            VehicleQRCode.objects.filter(code=qc).values_list("vehicle_id", flat=True).first()
        )

        for row in ConnectScanLog.objects.filter(qr_code=qc, created_at__gte=since).select_related(
            "vehicle", "scanned_by"
        ):
            who = ""
            if row.scanned_by_id:
                who = f"scanner user {row.scanned_by.username} ({row.scanned_by_id})"
            else:
                who = "anonymous"
            events.append(
                {
                    "at": row.created_at,
                    "kind": "scan",
                    "title": "QR scanned",
                    "detail": f"{who} · IP {row.ip_address or '—'}",
                    "ref_id": row.id,
                }
            )

        for row in ConnectQrOnboardLog.objects.filter(qr_code=qc, created_at__gte=since).select_related(
            "user", "vehicle"
        ):
            vn = row.vehicle.registration_number if row.vehicle_id else "—"
            events.append(
                {
                    "at": row.created_at,
                    "kind": "onboard",
                    "title": "Scanner onboard / verify",
                    "detail": f"User {row.user.username} ({row.user_id}) · vehicle {vn} · new={row.is_new_user}",
                    "ref_id": row.id,
                }
            )

        for row in ConnectCallLog.objects.filter(qr_code=qc, created_at__gte=since):
            events.append(
                {
                    "at": row.created_at,
                    "kind": "call",
                    "title": "Call attempt",
                    "detail": f"success={row.success} · owner_id={row.owner_id or '—'} · vehicle_id={row.vehicle_id or '—'}",
                    "ref_id": row.id,
                }
            )

        if vehicle_id:
            for row in (
                ConnectMessage.objects.filter(
                    thread__vehicle_id=vehicle_id,
                    created_at__gte=since,
                    message_type="text",
                )
                .select_related("sender", "thread")
                .order_by("-created_at")[:500]
            ):
                preview = (row.body or "")[:160]
                events.append(
                    {
                        "at": row.created_at,
                        "kind": "message",
                        "title": f"Chat message (thread #{row.thread_id})",
                        "detail": f"From {row.sender.username} ({row.sender_id}): {preview}",
                        "ref_id": row.id,
                    }
                )
    else:
        uid = user_id

        for row in ConnectScanLog.objects.filter(
            scanned_by_id=uid, created_at__gte=since
        ).select_related("vehicle"):
            events.append(
                {
                    "at": row.created_at,
                    "kind": "scan",
                    "title": "QR scanned",
                    "detail": f"QR {row.qr_code[:48]}… · vehicle {row.vehicle_id or '—'}",
                    "ref_id": row.id,
                }
            )

        for row in ConnectQrOnboardLog.objects.filter(user_id=uid, created_at__gte=since).select_related(
            "vehicle"
        ):
            vn = row.vehicle.registration_number if row.vehicle_id else "—"
            events.append(
                {
                    "at": row.created_at,
                    "kind": "onboard",
                    "title": "Scanner onboard / verify",
                    "detail": f"QR {row.qr_code[:48]}… · {vn} · new={row.is_new_user}",
                    "ref_id": row.id,
                }
            )

        for row in ConnectMessage.objects.filter(
            sender_id=uid, created_at__gte=since, message_type="text"
        ).select_related("thread", "thread__vehicle"):
            reg = ""
            if row.thread and row.thread.vehicle_id:
                reg = row.thread.vehicle.registration_number or ""
            events.append(
                {
                    "at": row.created_at,
                    "kind": "message",
                    "title": f"Chat sent (thread #{row.thread_id})",
                    "detail": f"{reg} · {(row.body or '')[:160]}",
                    "ref_id": row.id,
                }
            )

        for row in ConnectCallLog.objects.filter(owner_id=uid, created_at__gte=since):
            events.append(
                {
                    "at": row.created_at,
                    "kind": "call",
                    "title": "Call (as vehicle owner)",
                    "detail": f"QR {row.qr_code[:32] or '—'}… · success={row.success}",
                    "ref_id": row.id,
                }
            )

    events.sort(key=lambda x: x["at"], reverse=True)
    return events[:limit]
