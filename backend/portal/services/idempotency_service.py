"""
Strong idempotency for money-moving APIs: execute at most once per key.
Reserve idempotency key at request START (PENDING); only the request that reserves
may run business logic. Complete with response or mark FAILED on exception.
"""
import hashlib
import json
from typing import Optional, Tuple
from django.utils import timezone
from django.db import transaction, IntegrityError

from portal.models import IdempotencyRecord


# TTL for idempotency records (24 hours); replay returns stored response within TTL
IDEMPOTENCY_TTL_HOURS = 24


def get_idempotency_key(request) -> Optional[str]:
    """
    Extract idempotency key from X-Idempotency-Key header or body idempotency_key.
    Returns None if not provided (request is not idempotent).
    """
    key = request.META.get("HTTP_X_IDEMPOTENCY_KEY") or request.META.get("HTTP_IDEMPOTENCY_KEY")
    if key and isinstance(key, str) and key.strip():
        return key.strip()
    if getattr(request, "data", None) and isinstance(request.data, dict):
        key = request.data.get("idempotency_key")
        if key and isinstance(key, str) and key.strip():
            return key.strip()
    return None


def build_request_fingerprint(request) -> Optional[str]:
    """
    Build stable SHA-256 fingerprint from POST body for idempotency-key reuse checks.
    """
    if request.method != "POST":
        return None
    payload = {}
    if getattr(request, "data", None) and isinstance(request.data, dict):
        payload = dict(request.data)
    payload.pop("idempotency_key", None)
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_scope(partner_id: int, endpoint: str) -> str:
    """Scope = partner_id + endpoint so keys are per-partner per-endpoint."""
    return f"partner_{partner_id}:{endpoint}"


def reserve_idempotency(
    scope: str,
    idempotency_key: str,
    request_fingerprint: Optional[str] = None,
) -> Tuple[str, Optional[Tuple[int, str]]]:
    """
    At request start: try to INSERT (scope, idempotency_key, status=PENDING).
    Returns:
      ('reserved', None) - this request won the reservation; only it may execute business logic.
      ('replay', (status_code, body)) - record exists and is COMPLETED; return stored response.
      ('conflict', None) - record exists and is PENDING or FAILED; return 409.
    Uses transaction.atomic() so that INSERT and existing-record check are serialized.
    """
    with transaction.atomic():
        try:
            with transaction.atomic():
                IdempotencyRecord.objects.create(
                    scope=scope,
                    idempotency_key=idempotency_key,
                    status=IdempotencyRecord.STATUS_PENDING,
                    request_fingerprint=request_fingerprint,
                )
                return ("reserved", None)
        except IntegrityError:
            pass
        record = (
            IdempotencyRecord.objects.filter(
                scope=scope,
                idempotency_key=idempotency_key,
            )
            .order_by("-created_at")
            .first()
        )
        if not record:
            return ("conflict", None)
        if (
            request_fingerprint
            and record.request_fingerprint
            and record.request_fingerprint != request_fingerprint
        ):
            return ("fingerprint_mismatch", None)
        if record.status == IdempotencyRecord.STATUS_COMPLETED and record.response_http_status is not None and record.response_body is not None:
            return ("replay", (record.response_http_status, record.response_body))
        # PENDING or FAILED: another request is in progress or failed; client should not retry same key
        return ("conflict", None)


def complete_idempotency(
    scope: str,
    idempotency_key: str,
    response_http_status: int,
    response_body: str,
) -> None:
    """
    After successful execution: update record to COMPLETED and store response.
    Call only for the request that reserved the key.
    """
    IdempotencyRecord.objects.filter(
        scope=scope,
        idempotency_key=idempotency_key,
        status=IdempotencyRecord.STATUS_PENDING,
    ).update(
        status=IdempotencyRecord.STATUS_COMPLETED,
        response_http_status=response_http_status,
        response_body=response_body,
    )


def fail_idempotency(scope: str, idempotency_key: str) -> None:
    """
    On exception: mark record as FAILED so client gets 409 on replay (optional).
    Call only for the request that reserved the key.
    """
    IdempotencyRecord.objects.filter(
        scope=scope,
        idempotency_key=idempotency_key,
        status=IdempotencyRecord.STATUS_PENDING,
    ).update(status=IdempotencyRecord.STATUS_FAILED)


def get_cached_response(scope: str, idempotency_key: str) -> Optional[Tuple[int, str]]:
    """
    Return (response_http_status, response_body) if a COMPLETED record exists (within TTL).
    Used for backward compatibility; strong idempotency uses reserve_idempotency for replay.
    """
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(hours=IDEMPOTENCY_TTL_HOURS)
    record = (
        IdempotencyRecord.objects.filter(
            scope=scope,
            idempotency_key=idempotency_key,
            status=IdempotencyRecord.STATUS_COMPLETED,
            created_at__gte=cutoff,
        )
        .order_by("-created_at")
        .first()
    )
    if record and record.response_http_status is not None and record.response_body is not None:
        return record.response_http_status, record.response_body
    return None
