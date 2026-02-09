"""
Register step handlers for ServiceExecutionEngine.

Handlers are (vendor_code, api_code) -> callable(step, context, payload) -> {success, result, error}.
Register here so execution works when ServiceFlowStep rows are configured in admin.
"""
import logging
from portal.services.execution_engine import register_handler

logger = logging.getLogger(__name__)


def _paypoint_aeps_handler(step, context, payload):
    """Generic handler: call PayPoint AEPS client method matching step.vendor_api.api_code."""
    from portal.services.vendors.paypoint import PayPointAEPSClient
    client = PayPointAEPSClient()
    if not client.is_configured():
        return {"success": False, "result": None, "error": "PayPoint AEPS not configured"}
    api_code = (step.vendor_api.api_code or "").strip().lower()
    try:
        if api_code == "balance_enquiry":
            r = client.balance_enquiry(
                aadhaar_number=payload.get("aadhaar_number", ""),
                mobile_number=payload.get("mobile_number", ""),
                bank_iin=payload.get("bank_iin", ""),
                rd_request=payload.get("rd_request", ""),
                latitude=payload.get("latitude", ""),
                longitude=payload.get("longitude", ""),
                terminal_id=payload.get("terminal_id"),
                extra_params=payload.get("extra_params"),
            )
        elif api_code == "cash_withdrawal":
            r = client.cash_withdrawal(
                aadhaar_number=payload.get("aadhaar_number", ""),
                mobile_number=payload.get("mobile_number", ""),
                bank_iin=payload.get("bank_iin", ""),
                rd_request=payload.get("rd_request", ""),
                amount=payload.get("amount", ""),
                latitude=payload.get("latitude", ""),
                longitude=payload.get("longitude", ""),
                terminal_id=payload.get("terminal_id"),
                client_ref_id=payload.get("client_ref_id"),
                extra_params=payload.get("extra_params"),
            )
        elif api_code == "mini_statement":
            r = client.mini_statement(
                aadhaar_number=payload.get("aadhaar_number", ""),
                mobile_number=payload.get("mobile_number", ""),
                bank_iin=payload.get("bank_iin", ""),
                rd_request=payload.get("rd_request", ""),
                latitude=payload.get("latitude", ""),
                longitude=payload.get("longitude", ""),
                terminal_id=payload.get("terminal_id"),
                extra_params=payload.get("extra_params"),
            )
        elif api_code == "transaction_status":
            r = client.transaction_status(ref_id=payload.get("ref_id", ""))
        elif api_code == "agent_registration":
            r = client.agent_registration(
                agent_name=payload.get("agent_name"),
                mobile_number=payload.get("mobile_number"),
                email=payload.get("email"),
                extra=payload.get("extra"),
            )
        elif api_code in ("update_agent_details", "update_agent"):
            r = client.update_agent_details(
                agent_id=payload.get("agent_id"),
                agent_name=payload.get("agent_name"),
                mobile_number=payload.get("mobile_number"),
                email=payload.get("email"),
                extra=payload.get("extra"),
            )
        elif api_code in ("agent_service_status", "check_agent_service_status"):
            r = client.check_agent_service_status(
                agent_id=payload.get("agent_id"),
                extra=payload.get("extra"),
            )
        elif api_code in ("agent_authentication", "check_agent_authentication"):
            r = client.check_agent_authentication(
                agent_id=payload.get("agent_id"),
                extra=payload.get("extra"),
            )
        elif api_code in ("two_factor_authentication", "2fa", "two_factor_auth"):
            r = client.two_factor_authentication(
                agent_id=payload.get("agent_id"),
                otp=payload.get("otp"),
                extra=payload.get("extra"),
            )
        else:
            return {"success": False, "result": None, "error": f"Unknown PayPoint AEPS api_code: {api_code}"}
        ok = r.get("success", False)
        return {"success": ok, "result": r, "error": None if ok else r.get("error", r.get("message", "Unknown error"))}
    except Exception as e:
        logger.exception("PayPoint AEPS handler failed: %s", e)
        return {"success": False, "result": None, "error": str(e)}


def _paypoint_dmt_handler(step, context, payload):
    """Call PayPoint DMT client method matching step.vendor_api.api_code."""
    try:
        from portal.services.vendors.paypoint_dmt import PayPointDMTClient
    except ImportError:
        return {"success": False, "result": None, "error": "PayPoint DMT client not available"}
    client = PayPointDMTClient()
    if not client.is_configured():
        return {"success": False, "result": None, "error": "PayPoint DMT not configured"}
    api_code = (step.vendor_api.api_code or "").strip().lower()
    try:
        if api_code == "register_sender":
            r = client.register_sender(
                mobile_number=payload.get("mobile_number", ""),
                first_name=payload.get("first_name", ""),
                last_name=payload.get("last_name", ""),
                pincode=payload.get("pincode"),
                state=payload.get("state"),
                address=payload.get("address"),
                date_of_birth=payload.get("date_of_birth"),
                extra=payload.get("extra"),
            )
        elif api_code == "add_beneficiary":
            r = client.add_beneficiary(
                sender_mobile=payload.get("sender_mobile", ""),
                beneficiary_name=payload.get("beneficiary_name", ""),
                account_number=payload.get("account_number", ""),
                ifsc=payload.get("ifsc", ""),
                mobile_number=payload.get("mobile_number"),
                bank_name=payload.get("bank_name"),
                extra=payload.get("extra"),
            )
        elif api_code == "remit":
            r = client.remit(
                sender_mobile=payload.get("sender_mobile", ""),
                beneficiary_id=payload.get("beneficiary_id", ""),
                amount=payload.get("amount", ""),
                client_ref_id=payload.get("client_ref_id"),
                remarks=payload.get("remarks"),
                extra=payload.get("extra"),
            )
        elif api_code in ("transaction_status", "status"):
            r = client.transaction_status(ref_id=payload.get("ref_id", ""))
        elif api_code in ("get_beneficiaries", "beneficiaries"):
            r = client.get_beneficiaries(
                sender_mobile=payload.get("sender_mobile", ""),
                extra=payload.get("extra"),
            )
        else:
            return {"success": False, "result": None, "error": f"Unknown PayPoint DMT api_code: {api_code}"}
        ok = r.get("success", False)
        return {"success": ok, "result": r, "error": None if ok else r.get("error", r.get("message", "Unknown error"))}
    except Exception as e:
        logger.exception("PayPoint DMT handler failed: %s", e)
        return {"success": False, "result": None, "error": str(e)}


def register_default_handlers():
    """Register PayPoint AEPS and DMT handlers so ServiceExecutionEngine works when flow steps are configured."""
    # PayPoint AEPS
    for api_code in (
        "balance_enquiry", "cash_withdrawal", "mini_statement", "transaction_status",
        "agent_registration", "update_agent_details", "update_agent",
        "agent_service_status", "check_agent_service_status",
        "agent_authentication", "check_agent_authentication",
        "two_factor_authentication", "2fa", "two_factor_auth",
    ):
        register_handler("paypoint", api_code, _paypoint_aeps_handler)
    # PayPoint DMT
    for api_code in ("register_sender", "add_beneficiary", "remit", "transaction_status", "status", "get_beneficiaries", "beneficiaries"):
        register_handler("paypoint_dmt", api_code, _paypoint_dmt_handler)
    logger.info("Registered default step handlers for paypoint (AEPS) and paypoint_dmt (DMT)")
