"""
API Management (Registry + Logs) - Admin only views.
Product-level ON/OFF per platform (Parkpe / Payswap) – one toggle per product (e.g. Mobikwik BBPS).
"""
from django.shortcuts import redirect, get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views import View
from django.views.generic import ListView, TemplateView
from django.contrib import messages
from django.http import JsonResponse
from django.utils.decorators import method_decorator


def _is_api_registry_admin(user):
    if not user or not user.is_authenticated:
        return False
    return getattr(user, "role_code", "").lower() in ("admin", "super")


class APIProductListView(TemplateView):
    """
    Main API control: two cards – Parkpe and Payswap.
    Each card lists products (e.g. Mobikwik BBPS, Euronet BBPS) with one toggle per product.
    """
    template_name = "portal/api_registry/product_list.html"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _is_api_registry_admin(request.user):
            messages.error(request, "Access denied. Admin or Super role required.")
            return redirect("/dashboard/admin/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from api_management.models import APIProduct
        ctx = super().get_context_data(**kwargs)
        products = list(APIProduct.objects.order_by("platform", "display_order", "name"))
        parkpe = [p for p in products if p.platform == APIProduct.PLATFORM_PARKPE]
        payswap = [p for p in products if p.platform == APIProduct.PLATFORM_PAYSWAP]
        ctx["parkpe_products"] = parkpe
        ctx["payswap_products"] = payswap
        return ctx


class APIProductToggleView(View):
    """POST to toggle product enabled ON/OFF. Admin/Super only."""

    @method_decorator(login_required)
    @method_decorator(require_http_methods(["POST"]))
    def dispatch(self, request, *args, **kwargs):
        if not _is_api_registry_admin(request.user):
            return JsonResponse({"success": False, "message": "Access denied"}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        from api_management.models import APIProduct
        product = get_object_or_404(APIProduct, pk=pk)
        product.enabled = not product.enabled
        product.save()
        messages.success(request, f"{product.name} ({product.get_platform_display()}) is now {'ON' if product.enabled else 'OFF'}.")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True, "enabled": product.enabled})
        return redirect("api_product_list")


class APIRegistryListView(ListView):
    """List all APIs in the registry with status toggle. Admin/Super only."""
    template_name = "portal/api_registry/list.html"
    context_object_name = "apis"
    paginate_by = 25

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _is_api_registry_admin(request.user):
            messages.error(request, "Access denied. Admin or Super role required.")
            return redirect("/dashboard/admin/")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        from api_management.models import APIRegistry
        qs = APIRegistry.objects.select_related("service_category").order_by("version", "module_name", "api_name")
        version = self.request.GET.get("version")
        status_filter = self.request.GET.get("status")
        if version:
            qs = qs.filter(version=version)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class APIRegistryToggleView(View):
    """POST to toggle API status ON/OFF. Admin/Super only."""

    @method_decorator(login_required)
    @method_decorator(require_http_methods(["POST"]))
    def dispatch(self, request, *args, **kwargs):
        if not _is_api_registry_admin(request.user):
            return JsonResponse({"success": False, "message": "Access denied"}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, pk):
        from api_management.models import APIRegistry
        api = get_object_or_404(APIRegistry, pk=pk)
        api.status = APIRegistry.STATUS_OFF if api.status == APIRegistry.STATUS_ON else APIRegistry.STATUS_ON
        api.updated_by = request.user
        api.save()
        messages.success(request, f"API {api.api_name} is now {api.status}.")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True, "status": api.status})
        return redirect("api_registry_list")


class APILogListView(ListView):
    """List API logs with filters. Admin/Super only."""
    template_name = "portal/api_registry/log_list.html"
    context_object_name = "logs"
    paginate_by = 50

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _is_api_registry_admin(request.user):
            messages.error(request, "Access denied. Admin or Super role required.")
            return redirect("/dashboard/admin/")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        from api_management.models import APILog
        qs = APILog.objects.select_related("api_registry", "user").order_by("-created_at")
        status_code = self.request.GET.get("status_code")
        request_id = self.request.GET.get("request_id")
        if status_code:
            qs = qs.filter(status_code=status_code)
        if request_id:
            qs = qs.filter(request_id__icontains=request_id)
        return qs
