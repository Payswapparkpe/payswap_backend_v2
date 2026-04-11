"""
/services/ – Integrated vendors and their services.
Shows which vendors are integrated and which services they power.
"""
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.contrib import messages

from portal.models import ServiceFlowStep


def _is_services_admin(user):
    if not user or not user.is_authenticated:
        return False
    return getattr(user, "role_code", "").lower() in ("super_admin", "admin")


class ServicesIntegratedView(TemplateView):
    """
    GET /services/
    Integrated vendors & services (from ServiceFlowStep).
    """
    template_name = "portal/services/integrated.html"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _is_services_admin(request.user):
            messages.error(request, "Access denied. Admin or Super Admin required.")
            return redirect("/dashboard/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from django.db.models import Count

        ctx = super().get_context_data(**kwargs)

        # (1) Integrated vendors & services: distinct (vendor, service) from ServiceFlowStep
        steps = (
            ServiceFlowStep.objects
            .select_related("vendor", "service")
            .values("vendor_id", "vendor__code", "vendor__name", "service_id", "service__code", "service__name")
            .distinct()
        )
        # Group by vendor: vendor -> list of (service_code, service_name)
        by_vendor = {}
        for s in steps:
            vcode = s["vendor__code"]
            if vcode not in by_vendor:
                by_vendor[vcode] = {
                    "name": s["vendor__name"],
                    "code": vcode,
                    "services": [],
                }
            by_vendor[vcode]["services"].append({
                "code": s["service__code"],
                "name": s["service__name"],
            })

        # Dedupe services per vendor (same service can appear in multiple steps)
        for v in by_vendor.values():
            seen = set()
            unique = []
            for svc in v["services"]:
                key = svc["code"]
                if key not in seen:
                    seen.add(key)
                    unique.append(svc)
            v["services"] = unique

        # (2) Per vendor: count of VendorApis used in that vendor's flow steps
        vendor_api_count = (
            ServiceFlowStep.objects
            .values("vendor__code")
            .annotate(api_count=Count("vendor_api_id", distinct=True))
        )
        api_count_by_vendor = {r["vendor__code"]: r["api_count"] for r in vendor_api_count}
        for v in by_vendor.values():
            v["api_count"] = api_count_by_vendor.get(v["code"], 0)

        ctx["vendors_integrated"] = sorted(by_vendor.values(), key=lambda x: x["name"])
        ctx["platform"] = (self.request.GET.get("platform") or "").strip().lower()
        if ctx["platform"] not in ("parkpe", "payswap"):
            ctx["platform"] = None

        return ctx
