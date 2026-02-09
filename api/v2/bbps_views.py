"""
BBPS (Bharat Bill Payment System) APIs for External Partners (API v2)
Vendor is determined by partner's assigned vendor (VendorRouter). Admin assigns vendors per partner.
Product-level ON/OFF (Parkpe/Payswap): when product (e.g. Mobikwik BBPS) is OFF for a platform, API returns 503.
All endpoints require API key and bbps service permission.
"""
from rest_framework import views, status
from rest_framework.parsers import JSONParser

from api.mixins.response_mixin import StandardResponseMixin
from api.v2.authentication import APIKeyAuthentication
from api.v2.permissions import HasAPIKey, HasServicePermission, HasVendorAccess
from api.v2.throttling import APIKeyRateThrottle, ServiceRateThrottle
from api.v2.vendor_router import VendorRouter
from api_management.product_control import is_product_enabled
from portal.models import LogEntry
from portal.services.bbps_service import BBPSService
from portal.utils.logging_helper import get_logger
from portal.utils.ip_utils import get_client_ip, get_user_agent
from .serializers import (
    BBPSFetchBillSerializer,
    BBPSPayBillSerializer,
)

logger = get_logger("api.v2.bbps_views")

# Map BBPS vendor code to API product slug (used for product-level toggle)
BBPS_VENDOR_TO_PRODUCT_SLUG = {"mobikwik": "mobikwik_bbps", "euronet": "euronet_bbps"}


def _log_bbps_api(request, action, success, message, extra_data=None, vendor=None):
    """Create LogEntry for API v2 BBPS calls. category: euronet_bbps or mobikwik_bbps."""
    try:
        level = "INFO" if success else "ERROR"
        category = "euronet_bbps" if vendor == "euronet" else "mobikwik_bbps"
        extra = dict(extra_data or {}, action=action, success=success, source="api_v2")
        if vendor:
            extra["vendor"] = vendor
        LogEntry.objects.create(
            log_level=level,
            category=category,
            message=(message or "")[:500],
            module_name="api.v2.bbps_views",
            url=request.path if request else None,
            user=request.user if request and getattr(request, "user", None) and request.user.is_authenticated else None,
            client_ip=get_client_ip(request) if request else None,
            user_agent=get_user_agent(request) if request else None,
            extra_data=extra,
        )
    except Exception:
        pass


class BBPSOperatorsView(StandardResponseMixin, views.APIView):
    """
    Get list of BBPS operators/billers.
    Vendor is taken from partner's assigned vendor (admin-assigned).
    GET /api/v2/bbps/operators/?category=ELECTRICITY
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "bbps"
    required_action = "operators"

    def get(self, request):
        category = request.query_params.get("category") or None
        vendor_obj = VendorRouter.get_vendor_for_request(request, "bbps")
        vendor = vendor_obj.code
        product_slug = BBPS_VENDOR_TO_PRODUCT_SLUG.get(vendor) or f"{vendor}_bbps"
        if not is_product_enabled(None, product_slug, request):
            return self.error_response(
                message=f"BBPS product ({product_slug}) is disabled for this platform. Contact admin.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        service = BBPSService(vendor=vendor)
        if not service.is_available():
            return self.error_response(
                message="BBPS service is not configured or enabled for this vendor",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        result = service.get_operators(category=category)
        if not result.get("success"):
            _log_bbps_api(request, "operators", False, result.get("message", "Failed to fetch operators"), {"category": category}, vendor=result.get("vendor") or vendor)
            return self.error_response(
                message=result.get("message", "Failed to fetch operators"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        _log_bbps_api(request, "operators", True, f"Operators fetched: {len(result.get('operators', []))} items", {"category": category}, vendor=result.get("vendor"))
        return self.success_response(
            message="Operators fetched",
            data={"operators": result["operators"], "vendor": result.get("vendor", "mobikwik")},
            request=request,
        )


class BBPSFetchBillView(StandardResponseMixin, views.APIView):
    """
    Fetch BBPS bill details.
    Vendor is taken from partner's assigned vendor.
    POST /api/v2/bbps/bill/fetch/ body: operator_id, customer_id, subscriber_id?, ad1?, ad2?, ...
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "bbps"
    required_action = "fetch_bill"

    def post(self, request):
        serializer = BBPSFetchBillSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        data = serializer.validated_data
        vendor_obj = VendorRouter.get_vendor_for_request(request, "bbps")
        vendor = vendor_obj.code
        product_slug = BBPS_VENDOR_TO_PRODUCT_SLUG.get(vendor) or f"{vendor}_bbps"
        if not is_product_enabled(None, product_slug, request):
            return self.error_response(
                message=f"BBPS product ({product_slug}) is disabled for this platform. Contact admin.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        service = BBPSService(vendor=vendor)
        if not service.is_available():
            return self.error_response(
                message="BBPS service is not configured or enabled for this vendor",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        extra = {}
        for k in ("ad1", "ad2", "ad3", "ad4", "ad9"):
            v = data.get(k)
            if v not in (None, ""):
                extra[k] = str(v).strip()
        result = service.fetch_bill(
            operator_id=data["operator_id"],
            customer_id=data["customer_id"],
            subscriber_id=data.get("subscriber_id") or None,
            extra=extra if extra else None,
        )
        if not result.get("success"):
            _log_bbps_api(request, "fetch_bill", False, result.get("message", "Bill fetch failed"), {"operator_id": data.get("operator_id")}, vendor=result.get("vendor") or vendor)
            return self.error_response(
                message=result.get("message", "Bill fetch failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        _log_bbps_api(request, "fetch_bill", True, "Bill fetched", {"operator_id": data.get("operator_id")}, vendor=result.get("vendor"))
        return self.success_response(
            message="Bill fetched",
            data={"bill_details": result["bill_details"], "vendor": result.get("vendor", "mobikwik")},
            request=request,
        )


class BBPSPayBillView(StandardResponseMixin, views.APIView):
    """
    Pay BBPS bill.
    Vendor is taken from partner's assigned vendor.
    POST /api/v2/bbps/bill/pay/ body: operator_id, customer_id, amount, ref_id, subscriber_id?, ad1?, ...
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "bbps"
    required_action = "pay_bill"

    def post(self, request):
        serializer = BBPSPayBillSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        data = serializer.validated_data
        vendor_obj = VendorRouter.get_vendor_for_request(request, "bbps")
        vendor = vendor_obj.code
        product_slug = BBPS_VENDOR_TO_PRODUCT_SLUG.get(vendor) or f"{vendor}_bbps"
        if not is_product_enabled(None, product_slug, request):
            return self.error_response(
                message=f"BBPS product ({product_slug}) is disabled for this platform. Contact admin.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        service = BBPSService(vendor=vendor)
        if not service.is_available():
            return self.error_response(
                message="BBPS service is not configured or enabled for this vendor",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        extra = {}
        for k in ("ad1", "ad2", "ad3", "ad4", "ad9"):
            v = data.get(k)
            if v not in (None, ""):
                extra[k] = str(v).strip()
        result = service.pay_bill(
            operator_id=data["operator_id"],
            customer_id=data["customer_id"],
            amount=str(data["amount"]),
            ref_id=data["ref_id"],
            subscriber_id=data.get("subscriber_id") or None,
            extra=extra if extra else None,
        )
        if not result.get("success"):
            _log_bbps_api(request, "pay_bill", False, result.get("message", "Payment failed"), {"operator_id": data.get("operator_id"), "ref_id": data.get("ref_id")}, vendor=result.get("vendor") or vendor)
            return self.error_response(
                message=result.get("message", "Payment failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        _log_bbps_api(request, "pay_bill", True, "Payment submitted", {"operator_id": data.get("operator_id"), "ref_id": data.get("ref_id")}, vendor=result.get("vendor"))
        return self.success_response(
            message="Payment submitted",
            data={
                "transaction_id": result.get("transaction_id"),
                "ref_id": data["ref_id"],
                "status": result.get("status"),
                "vendor": result.get("vendor", "mobikwik"),
            },
            request=request,
        )


class BBPSPaymentStatusView(StandardResponseMixin, views.APIView):
    """
    Get BBPS payment status by ref_id.
    Vendor is taken from partner's assigned vendor.
    GET /api/v2/bbps/bill/status/<ref_id>/
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "bbps"
    required_action = "payment_status"

    def get(self, request, ref_id):
        vendor_obj = VendorRouter.get_vendor_for_request(request, "bbps")
        vendor = vendor_obj.code
        product_slug = BBPS_VENDOR_TO_PRODUCT_SLUG.get(vendor) or f"{vendor}_bbps"
        if not is_product_enabled(None, product_slug, request):
            return self.error_response(
                message=f"BBPS product ({product_slug}) is disabled for this platform. Contact admin.",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        service = BBPSService(vendor=vendor)
        if not service.is_available():
            return self.error_response(
                message="BBPS service is not configured or enabled for this vendor",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        result = service.payment_status(ref_id=ref_id)
        if not result.get("success"):
            _log_bbps_api(request, "payment_status", False, result.get("message", "Status fetch failed"), {"ref_id": ref_id}, vendor=result.get("vendor") or vendor)
            return self.error_response(
                message=result.get("message", "Status fetch failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        _log_bbps_api(request, "payment_status", True, f"Status: {result.get('status', 'unknown')}", {"ref_id": ref_id}, vendor=result.get("vendor"))
        return self.success_response(
            message="Status fetched",
            data={
                "ref_id": ref_id,
                "status": result.get("status"),
                "vendor": result.get("vendor", "mobikwik"),
                "data": result.get("data"),
            },
            request=request,
        )
