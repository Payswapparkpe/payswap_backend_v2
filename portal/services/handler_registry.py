"""
Register step handlers for ServiceExecutionEngine.

Handlers are (vendor_code, api_code) -> callable(step, context, payload) -> {success, result, error}.
Register here so execution works when ServiceFlowStep rows are configured in admin.
"""
import logging
from portal.services.execution_engine import register_handler

logger = logging.getLogger(__name__)


def register_default_handlers():
    """Register default step handlers. AEPS/DMT (PayPoint) removed - no handlers to register."""
    pass
