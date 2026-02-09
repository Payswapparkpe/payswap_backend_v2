"""
API endpoints for vendor-orchestrated service flows.

- Vendors list and detail (with APIs)
- Services list
- Service flow (ordered steps) for frontend to render execution order
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from portal.models import ApiVendor, VendorApi, Service, ServiceFlowStep


class VendorListView(APIView):
    """GET /api/v2/vendors/ – List all API vendors."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendors = ApiVendor.objects.filter(is_active=True).order_by('name')
        data = [
            {
                "id": v.id,
                "name": v.name,
                "code": v.code,
                "description": v.description or "",
                "is_active": v.is_active,
            }
            for v in vendors
        ]
        return Response({"vendors": data, "count": len(data)})


class VendorDetailView(APIView):
    """GET /api/v2/vendors/<code>/ – Vendor detail with its APIs."""
    permission_classes = [IsAuthenticated]

    def get(self, request, vendor_code):
        try:
            vendor = ApiVendor.objects.get(code=vendor_code, is_active=True)
        except ApiVendor.DoesNotExist:
            return Response({"detail": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)
        apis = VendorApi.objects.filter(vendor=vendor, is_active=True).order_by('api_code')
        data = {
            "id": vendor.id,
            "name": vendor.name,
            "code": vendor.code,
            "description": vendor.description or "",
            "is_active": vendor.is_active,
            "apis": [
                {
                    "id": a.id,
                    "name": a.name,
                    "api_code": a.api_code,
                    "api_type": a.api_type,
                    "http_method": a.http_method,
                    "timeout_seconds": a.timeout_seconds,
                    "retry_allowed": a.retry_allowed,
                }
                for a in apis
            ],
        }
        return Response(data)


class ServiceListView(APIView):
    """GET /api/v2/services/ – List services (final products). Optional ?category=AEPS."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Service.objects.all().order_by('name')
        category = request.query_params.get('category')
        if category:
            qs = qs.filter(category__iexact=category)
        data = [
            {
                "id": s.id,
                "name": s.name,
                "code": s.code,
                "category": s.category or "",
                "description": (s.description or "")[:200],
                "status": s.status,
                "is_enabled": s.is_enabled,
            }
            for s in qs
        ]
        return Response({"services": data, "count": len(data)})


class ServiceFlowView(APIView):
    """GET /api/v2/services/<code>/flow/ – Ordered flow steps for a service. Frontend must NOT guess order."""
    permission_classes = [IsAuthenticated]

    def get(self, request, service_code):
        try:
            service = Service.objects.get(code=service_code)
        except Service.DoesNotExist:
            return Response({"detail": "Service not found."}, status=status.HTTP_404_NOT_FOUND)
        steps = (
            ServiceFlowStep.objects.filter(service=service)
            .select_related("vendor", "vendor_api")
            .order_by("step_order")
        )
        data = {
            "service": {
                "id": service.id,
                "name": service.name,
                "code": service.code,
                "category": service.category or "",
            },
            "steps": [
                {
                    "step_order": s.step_order,
                    "step_name": s.step_name,
                    "vendor": {
                        "id": s.vendor.id,
                        "name": s.vendor.name,
                        "code": s.vendor.code,
                    },
                    "vendor_api": {
                        "id": s.vendor_api.id,
                        "name": s.vendor_api.name,
                        "api_code": s.vendor_api.api_code,
                        "api_type": s.vendor_api.api_type,
                    },
                    "is_mandatory": s.is_mandatory,
                    "halt_on_failure": s.halt_on_failure,
                }
                for s in steps
            ],
        }
        return Response(data)
