"""
Connect abuse controls and lightweight risk scoring.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from api.utils.client_ip import get_client_ip


@dataclass
class RiskDecision:
    allowed: bool
    score: int
    reasons: list[str]
    challenge_required: bool = False


def request_fingerprint(request) -> str:
    ip = get_client_ip(request) or "0.0.0.0"
    ua = (request.META.get("HTTP_USER_AGENT") or "")[:250]
    raw = f"{ip}|{ua}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _bucket() -> str:
    return timezone.now().strftime("%Y%m%d%H")


def _limit_key(scope: str, subject: str, suffix: str = "") -> str:
    extra = f":{suffix}" if suffix else ""
    return f"connect_risk:{scope}:{subject}:{_bucket()}{extra}"


def _increment_counter(key: str, ttl_seconds: int = 3900) -> int:
    value = cache.get(key)
    if value is None:
        cache.set(key, 1, timeout=ttl_seconds)
        return 1
    try:
        value = int(value) + 1
    except (TypeError, ValueError):
        value = 1
    cache.set(key, value, timeout=ttl_seconds)
    return value


def _get_limit(name: str, default: int) -> int:
    try:
        return int(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default


def check_call_abuse(
    request,
    *,
    scanner_user_id: int | None,
    scanner_phone: str,
    owner_id: int | None,
    qr_code: str,
) -> RiskDecision:
    reasons: list[str] = []
    score = 0

    fingerprint = request_fingerprint(request)
    phone_suffix = scanner_phone[-10:] if scanner_phone else "unknown"
    call_user_limit = _get_limit("CONNECT_CALL_MAX_PER_USER_HOUR", 8)
    call_phone_limit = _get_limit("CONNECT_CALL_MAX_PER_PHONE_HOUR", 12)
    call_owner_limit = _get_limit("CONNECT_CALL_MAX_PER_OWNER_HOUR", 15)
    call_fp_limit = _get_limit("CONNECT_CALL_MAX_PER_FINGERPRINT_HOUR", 10)
    unique_targets_limit = _get_limit("CONNECT_CALL_MAX_UNIQUE_QR_PER_HOUR", 5)

    if scanner_user_id:
        count = _increment_counter(_limit_key("call_user", str(scanner_user_id)))
        if count > call_user_limit:
            reasons.append("user_hourly_limit")
            score += 35

    phone_count = _increment_counter(_limit_key("call_phone", phone_suffix))
    if phone_count > call_phone_limit:
        reasons.append("phone_hourly_limit")
        score += 30

    if owner_id:
        owner_count = _increment_counter(_limit_key("call_owner", str(owner_id)))
        if owner_count > call_owner_limit:
            reasons.append("owner_flood_protection")
            score += 25

    fp_count = _increment_counter(_limit_key("call_fp", fingerprint))
    if fp_count > call_fp_limit:
        reasons.append("fingerprint_hourly_limit")
        score += 35

    unique_targets_key = _limit_key("call_unique_qr_set", fingerprint)
    hashed_qr = hashlib.md5(qr_code.encode("utf-8")).hexdigest()[:8]
    targets = cache.get(unique_targets_key) or []
    if hashed_qr not in targets:
        targets = list(targets)[-50:] + [hashed_qr]
        cache.set(unique_targets_key, targets, timeout=3900)
    target_count = len(targets)
    if target_count > unique_targets_limit:
        reasons.append("multi_target_spread")
        score += 30

    hard_block = score >= 60
    challenge_required = 35 <= score < 60
    return RiskDecision(allowed=not hard_block, score=score, reasons=reasons, challenge_required=challenge_required)


def check_chat_abuse(
    request,
    *,
    sender_user_id: int,
    thread_id: int,
    recipient_user_id: int | None,
    body: str,
) -> RiskDecision:
    reasons: list[str] = []
    score = 0
    fingerprint = request_fingerprint(request)

    msg_user_limit = _get_limit("CONNECT_CHAT_MAX_PER_USER_HOUR", 80)
    msg_thread_limit = _get_limit("CONNECT_CHAT_MAX_PER_THREAD_HOUR", 35)
    msg_recipient_limit = _get_limit("CONNECT_CHAT_MAX_PER_RECIPIENT_HOUR", 45)
    max_body_len = _get_limit("CONNECT_CHAT_MAX_BODY_LENGTH", 500)

    if len(body) > max_body_len:
        reasons.append("message_too_long")
        score += 80

    user_count = _increment_counter(_limit_key("chat_user", str(sender_user_id)))
    if user_count > msg_user_limit:
        reasons.append("chat_user_hourly_limit")
        score += 35

    thread_count = _increment_counter(_limit_key("chat_thread", str(thread_id)))
    if thread_count > msg_thread_limit:
        reasons.append("chat_thread_flood")
        score += 30

    if recipient_user_id:
        recipient_count = _increment_counter(_limit_key("chat_recipient", str(recipient_user_id)))
        if recipient_count > msg_recipient_limit:
            reasons.append("chat_recipient_protection")
            score += 25

    fp_count = _increment_counter(_limit_key("chat_fp", fingerprint))
    if fp_count > _get_limit("CONNECT_CHAT_MAX_PER_FINGERPRINT_HOUR", 100):
        reasons.append("chat_fingerprint_limit")
        score += 30

    return RiskDecision(allowed=score < 60, score=score, reasons=reasons, challenge_required=False)


def report_unique_reporters_count(reported_user_id: int, *, within_hours: int = 24) -> int:
    from portal.models import ConnectReport  # local import to avoid startup coupling

    since = timezone.now() - timedelta(hours=within_hours)
    return (
        ConnectReport.objects.filter(reported_user_id=reported_user_id, created_at__gte=since)
        .values("reporter_user_id")
        .distinct()
        .count()
    )


def iso_now() -> str:
    return datetime.utcnow().isoformat() + "Z"
