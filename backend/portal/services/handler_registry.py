"""
Register step handlers for ServiceExecutionEngine.

Handlers are (vendor_code, api_code) -> callable(step, context, payload) -> {success, result, error}.
Register here so execution works when ServiceFlowStep rows are configured in admin.
"""
import logging
from portal.services.execution_engine import register_handler
from portal.services.api_registry import INSTANTPAY_HANDLER_API_CODES

logger = logging.getLogger(__name__)


def register_default_handlers():
    """Register default step handlers for orchestration engine."""
    from portal.services.instantpay_hub_service import InstantpayHubService

    service = InstantpayHubService()

    def _make_handler(api_code: str):
        def _handler(step, context, payload):
            partner_id = context.get("partner_id") or context.get("user_id")
            result = service.execute(
                api_code,
                payload,
                partner_id=partner_id,
                idempotency_key=(payload or {}).get("idempotency_key"),
            )
            return {
                "success": bool(result.get("success")),
                "result": result,
                "error": result.get("error") if not result.get("success") else None,
            }
        return _handler

    for code in INSTANTPAY_HANDLER_API_CODES:
        register_handler("instantpay", code, _make_handler(code))
