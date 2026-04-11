"""
Strong idempotency for API v2 money-moving endpoints: execute at most once per key.
Reserve idempotency key at request START (PENDING); only the request that reserves
may run business logic. Replay returns stored response; concurrent duplicate returns 409.
"""
from django.http import HttpResponse
from rest_framework import status as http_status

from portal.services.idempotency_service import (
    get_idempotency_key,
    build_scope,
    reserve_idempotency,
    complete_idempotency,
    fail_idempotency,
)


class IdempotencyMixin:
    """
    Mixin for API v2 views that perform money-moving operations.
    Set idempotency_scope_suffix on the view class, e.g. "v2:voucher_issue".
    Only the request that successfully reserves the key (INSERT PENDING) runs business logic.
    """

    idempotency_scope_suffix = ""

    def dispatch(self, request, *args, **kwargs):
        if request.method != "POST":
            return super().dispatch(request, *args, **kwargs)

        partner = getattr(request, "partner", None)
        if not partner or not getattr(self, "idempotency_scope_suffix", None):
            return super().dispatch(request, *args, **kwargs)

        key = get_idempotency_key(request)
        if not key:
            return super().dispatch(request, *args, **kwargs)

        scope = build_scope(partner.id, self.idempotency_scope_suffix)

        # Strong idempotency: reserve at start; only reserved request may execute
        outcome, cached = reserve_idempotency(scope, key)
        if outcome == "replay" and cached:
            status_code, body = cached
            return HttpResponse(
                body,
                status=status_code,
                content_type="application/json",
            )
        if outcome == "conflict":
            return HttpResponse(
                '{"detail":"Idempotency key already in use or previous request failed. Use a new key or retry later."}',
                status=http_status.HTTP_409_CONFLICT,
                content_type="application/json",
            )

        # Reserved: only this request runs business logic
        try:
            response = super().dispatch(request, *args, **kwargs)
            try:
                body = response.content.decode("utf-8") if response.content else "{}"
                status_code = response.status_code
            except Exception:
                fail_idempotency(scope, key)
                return response
            complete_idempotency(scope, key, status_code, body)
            return response
        except Exception:
            fail_idempotency(scope, key)
            raise
