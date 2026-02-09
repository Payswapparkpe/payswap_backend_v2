"""
Service Execution Engine – data-driven, vendor-orchestrated flow execution.

Services are ordered steps (ServiceFlowStep); each step maps to a VendorApi.
Execution is driven by step_order; no hard-coded vendor logic in the engine.
Handlers are registered per (vendor_code, api_code) and invoked at runtime.
"""
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Type: (step, context, payload) -> {"success": bool, "result": Any, "error": Optional[str]}
StepHandler = Callable[[Any, Dict[str, Any], Dict[str, Any]], Dict[str, Any]]


class ServiceExecutionEngine:
    """
    Executes a service as an ordered sequence of vendor API steps.
    Input: service_code, user/agent, request_payload.
    Output: final result + per-step outcomes (no vendor-specific logic).
    """

    def __init__(self):
        self._registry: Dict[tuple, StepHandler] = {}  # (vendor_code, api_code) -> handler

    def register(self, vendor_code: str, api_code: str, handler: StepHandler) -> None:
        """Register a callable for (vendor_code, api_code). Same API can be reused across services."""
        key = (vendor_code.lower().strip(), api_code.lower().strip())
        self._registry[key] = handler
        logger.debug("Registered handler %s -> %s", key, handler.__name__)

    def get_handler(self, vendor_code: str, api_code: str) -> Optional[StepHandler]:
        """Get handler for (vendor_code, api_code). Returns None if not registered."""
        key = (vendor_code.lower().strip(), api_code.lower().strip())
        return self._registry.get(key)

    def execute(
        self,
        service_code: str,
        payload: Dict[str, Any],
        user_id: Optional[int] = None,
        agent_id: Optional[int] = None,
        request_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute service flow for the given service_code.
        1. Load ServiceFlowStep ordered by step_order.
        2. For each step: resolve handler, run, store outcome.
        3. If step fails and halt_on_failure -> stop and return.
        4. Return aggregated result with step_results and final outcome.
        """
        from portal.models import Service, ServiceFlowStep

        try:
            service = Service.objects.get(code=service_code)
        except Service.DoesNotExist:
            return {
                "success": False,
                "error": "service_not_found",
                "message": f"Service with code '{service_code}' not found.",
                "step_results": [],
                "final_result": None,
            }

        steps = list(
            ServiceFlowStep.objects.filter(service=service)
            .select_related("vendor", "vendor_api")
            .order_by("step_order")
        )
        if not steps:
            return {
                "success": False,
                "error": "no_flow_defined",
                "message": f"No flow steps defined for service '{service_code}'.",
                "step_results": [],
                "final_result": None,
            }

        context: Dict[str, Any] = {
            "user_id": user_id,
            "agent_id": agent_id,
            "service_code": service_code,
            "request_meta": request_meta or {},
        }
        step_results: List[Dict[str, Any]] = []
        final_result: Optional[Dict[str, Any]] = None

        for step in steps:
            vendor_code = step.vendor.code
            api_code = step.vendor_api.api_code
            handler = self.get_handler(vendor_code, api_code)

            if not handler:
                step_outcome = {
                    "step_order": step.step_order,
                    "step_name": step.step_name,
                    "vendor": vendor_code,
                    "api_code": api_code,
                    "success": False,
                    "skipped": True,
                    "error": "handler_not_registered",
                    "result": None,
                }
                step_results.append(step_outcome)
                if step.halt_on_failure and step.is_mandatory:
                    return {
                        "success": False,
                        "error": "handler_not_registered",
                        "message": f"No handler for {vendor_code}:{api_code} (step: {step.step_name})",
                        "step_results": step_results,
                        "final_result": None,
                    }
                continue

            try:
                outcome = handler(step, context, payload)
            except Exception as e:
                logger.exception("Step handler failed: %s", e)
                outcome = {"success": False, "result": None, "error": str(e)}

            success = outcome.get("success", False)
            result = outcome.get("result")
            error = outcome.get("error")

            if success and result:
                context[f"step_{step.step_order}"] = result
                context[f"step_{vendor_code}_{api_code}"] = result
                final_result = result

            step_outcome = {
                "step_order": step.step_order,
                "step_name": step.step_name,
                "vendor": vendor_code,
                "api_code": api_code,
                "success": success,
                "skipped": False,
                "error": error,
                "result": result,
            }
            step_results.append(step_outcome)

            if not success and step.halt_on_failure:
                return {
                    "success": False,
                    "error": error or "step_failed",
                    "message": f"Step {step.step_order} ({step.step_name}) failed.",
                    "step_results": step_results,
                    "final_result": final_result,
                }

        return {
            "success": True,
            "error": None,
            "message": "Flow completed.",
            "step_results": step_results,
            "final_result": final_result,
        }


# Global engine instance; handlers register on import or via app ready.
_engine: Optional[ServiceExecutionEngine] = None


def get_execution_engine() -> ServiceExecutionEngine:
    """Return the global ServiceExecutionEngine (lazy singleton)."""
    global _engine
    if _engine is None:
        _engine = ServiceExecutionEngine()
    return _engine


def register_handler(vendor_code: str, api_code: str, handler: StepHandler) -> None:
    """Register a step handler for (vendor_code, api_code)."""
    get_execution_engine().register(vendor_code, api_code, handler)
