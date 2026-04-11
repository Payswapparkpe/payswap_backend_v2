"""
Project Management – Parkpe and Payswap API keys. Internal apps only.
Admin and Super Admin only.
"""


def _is_project_admin(user):
    if not user or not user.is_authenticated:
        return False
    return getattr(user, "role_code", "").lower() in ("super_admin", "admin")


from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.views import View
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from portal.models import ResellerPartner
from portal.services.api_key_service import APIKeyService

# Full permissions for app API keys (same as ensure_parkpe_partner)
FULL_PERMISSIONS = {
    "voucher": {"issue": True, "redeem": True, "status": True, "view_sensitive": True},
    "bbps": {"operators": True, "fetch_bill": True, "pay_bill": True, "payment_status": True},
    "kyc": {
        "pan": True, "aadhaar": True, "bank": True, "driving_license": True,
        "voter_id": True, "passport": True, "gst": True, "face_match": True,
        "face_liveness": True, "status": True,
    },
    "sms": {"send": True, "otp_send": True, "otp_verify": True, "delivery_status": True},
    "payment": {"initiate": True, "status": True, "refund": True},
}


def _get_partner_or_create(partner_code: str):
    """Get ResellerPartner by partner_code; create Payswap partner if missing (Parkpe is created via ensure_parkpe_partner)."""
    partner = ResellerPartner.objects.filter(partner_code=partner_code, status="ACTIVE").first()
    if partner:
        return partner
    if partner_code == "payswap":
        partner, _ = ResellerPartner.objects.get_or_create(
            partner_code="payswap",
            defaults={
                "company_name": "Payswap",
                "contact_person": "Payswap Platform",
                "email": "payswap-partner@payswap.in",
                "phone": "0000000000",
                "status": "ACTIVE",
                "onboarding_status": "APPROVED",
            },
        )
        return partner
    return None  # parkpe not created here; use ensure_parkpe_partner


class ProjectManagementView(TemplateView):
    """
    Project Management dashboard: Parkpe and Payswap cards with links to
    API Control, Services (API ON/OFF), Hub RBAC, and API keys (list + create).
    """
    template_name = "portal/project_management/dashboard.html"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _is_project_admin(request.user):
            messages.error(request, "Access denied. Admin or Super Admin required.")
            return redirect("/dashboard/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        partner_parkpe = _get_partner_or_create("parkpe")
        partner_payswap = _get_partner_or_create("payswap")
        parkpe_keys = list(partner_parkpe.api_keys.all().order_by("-created_at")) if partner_parkpe else []
        payswap_keys = list(partner_payswap.api_keys.all().order_by("-created_at")) if partner_payswap else []

        ctx["parkpe"] = {
            "name": "Parkpe",
            "partner": partner_parkpe,
            "api_keys": parkpe_keys,
        }
        ctx["payswap"] = {
            "name": "Payswap",
            "partner": partner_payswap,
            "api_keys": payswap_keys,
        }

        # One-time display of newly created API key (from session, then clear)
        new_key = self.request.session.pop("new_api_key_plain", None)
        new_key_for = self.request.session.pop("new_api_key_for", None)
        ctx["new_api_key_plain"] = new_key
        ctx["new_api_key_for"] = new_key_for

        return ctx


class CreateProjectAPIKeyView(View):
    """POST: create a new API key for Parkpe or Payswap. Redirects back to project_management with key in session (show once)."""

    @method_decorator(login_required)
    @method_decorator(require_http_methods(["POST"]))
    def dispatch(self, request, *args, **kwargs):
        if not _is_project_admin(request.user):
            messages.error(request, "Access denied.")
            return redirect("/dashboard/")
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        partner_code = (request.POST.get("partner_code") or "").strip().lower()
        if partner_code not in ("parkpe", "payswap"):
            messages.error(request, "Invalid partner. Use parkpe or payswap.")
            return redirect("project_management")
        key_name = (request.POST.get("key_name") or f"{partner_code.title()} App").strip() or f"{partner_code.title()} App"

        partner = _get_partner_or_create(partner_code)
        if not partner:
            messages.error(request, f"Partner {partner_code} not found.")
            return redirect("project_management")

        try:
            created_by = request.user
            api_key_obj, plain_key, plain_secret = APIKeyService.create_api_key(
                partner=partner,
                key_name=key_name,
                key_type="LIVE",
                permissions=FULL_PERMISSIONS,
                rate_limits={},
                created_by=created_by,
            )
            request.session["new_api_key_plain"] = plain_key
            request.session["new_api_key_for"] = partner_code
            messages.success(request, f"API key created for {partner_code}. Copy it below – we won’t show it again.")
        except Exception as e:
            messages.error(request, f"Failed to create API key: {e}")
        return redirect("project_management")
