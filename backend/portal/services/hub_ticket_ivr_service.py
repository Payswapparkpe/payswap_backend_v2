"""
Hub support: Kaleyra click-to-call from ticket screen (agent/staff dials two numbers: from → to).
Reuses the same Kaleyra voice API as ParkPe Connect (see [KaleyraClient.click_to_call]).
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from django.http import HttpRequest

from portal.models import LogEntry, Ticket, User
from portal.utils.ip_utils import get_client_ip
from portal.utils.masking import mask_phone_for_log
from portal.utils.validators import normalize_phone_number


def _mask_pair(from_norm: str, to_norm: str) -> Dict[str, str]:
    return {
        "from_masked": mask_phone_for_log(from_norm),
        "to_masked": mask_phone_for_log(to_norm),
    }


# Roles allowed to start Hub IVR (list + detail); keep in sync with views.
HUB_IVR_ROLE_CODES = frozenset(
    {
        "super_admin",
        "admin",
        "employee",
        "fleet_admin",
        "fleet_manager",
        "fleet_operator",
        "fleet_dispatcher",
    }
)


def user_may_use_hub_ivr(user: User) -> bool:
    return getattr(user, "role_code", None) in HUB_IVR_ROLE_CODES


def initiate_hub_ticket_ivr(
    *,
    from_raw: str,
    to_raw: str,
    ticket: Optional[Ticket],
    actor: User,
    request: Optional[HttpRequest] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Initiate a Kaleyra click-to-call. First [from] rings, then bridges to [to].

    Returns:
        (success, user_message, raw_result_dict_or_none)
    """
    from_str = (from_raw or "").strip()
    to_str = (to_raw or "").strip()
    if not from_str or not to_str:
        return False, "Enter both numbers: who is calling and who to connect.", None

    try:
        from_norm = normalize_phone_number(from_str)
        to_norm = normalize_phone_number(to_str)
    except ValueError as e:
        return False, f"Invalid phone: {e}", None

    digits_from = "".join(c for c in from_norm if c.isdigit())
    digits_to = "".join(c for c in to_norm if c.isdigit())
    if digits_from == digits_to:
        return False, "From and to numbers must be different.", None

    from portal.services.hub_cost_service import record_hub_cost
    from portal.services.vendors.kaleyra import KaleyraClient

    client = KaleyraClient()
    if not client.api_key:
        return False, "Kaleyra API is not configured (missing API key).", None

    try:
        result = client.click_to_call(from_number=from_str, to_number=to_str)
    except Exception as e:
        err_msg = str(e)[:500]
        _write_hub_ivr_log(
            success=False,
            ticket=ticket,  # may be None (quick call from ticket list)
            actor=actor,
            request=request,
            from_norm=from_norm,
            to_norm=to_norm,
            message=f"Kaleyra click_to_call failed: {err_msg}",
            kaleyra_result=None,
        )
        return False, f"Could not start call: {err_msg}", None

    kaleyra_id = ""
    if isinstance(result, dict):
        kaleyra_id = str(result.get("call_id") or result.get("id") or "")[:128]

    try:
        record_hub_cost("ivr", "kaleyra", unit_count=1, reference_id=kaleyra_id or None)
    except Exception:
        pass

    _write_hub_ivr_log(
        success=True,
        ticket=ticket,
        actor=actor,
        request=request,
        from_norm=from_norm,
        to_norm=to_norm,
        message="Hub ticket IVR click-to-call initiated",
        kaleyra_result=result if isinstance(result, dict) else {"raw": str(result)[:200]},
    )

    msg = "Call leg initiated. The first number should ring first, then the second will connect (same flow as Connect)."
    if kaleyra_id:
        msg += f" Ref: {kaleyra_id[:32]}…"
    return True, msg, result if isinstance(result, dict) else None


def _write_hub_ivr_log(
    *,
    success: bool,
    ticket: Optional[Ticket],
    actor: User,
    request: Optional[HttpRequest],
    from_norm: str,
    to_norm: str,
    message: str,
    kaleyra_result: Optional[Dict[str, Any]],
) -> None:
    try:
        extra = {
            "action": "hub_ticket_ivr",
            "success": success,
            **_mask_pair(from_norm, to_norm),
        }
        if ticket is not None:
            extra["ticket_id"] = ticket.ticket_id
            extra["ticket_pk"] = ticket.pk
        else:
            extra["source"] = "tickets_list_quick"
            extra["ticket_id"] = None
            extra["ticket_pk"] = None
        if kaleyra_result and success:
            extra["kaleyra_call_id"] = str(
                kaleyra_result.get("call_id") or kaleyra_result.get("id") or ""
            )[:64]

        LogEntry.objects.create(
            log_level="INFO" if success else "ERROR",
            category="kaleyra",
            message=message[:500],
            module_name="portal.services.hub_ticket_ivr_service",
            url=(request.path if request else None) or "",
            user=actor,
            client_ip=get_client_ip(request) if request else None,
            extra_data=extra,
        )
    except Exception:
        pass
