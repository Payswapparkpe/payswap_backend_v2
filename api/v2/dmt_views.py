"""
DMT (Domestic Money Transfer) APIs for External Partners (API v2)
Uses PayPoint as DMT vendor. All endpoints require API key and dmt service permission.
"""
from rest_framework import views, status
from rest_framework.parsers import JSONParser

from api.mixins.response_mixin import StandardResponseMixin
from api.v2.authentication import APIKeyAuthentication
from api.v2.permissions import HasAPIKey, HasServicePermission, HasVendorAccess
from api.v2.throttling import APIKeyRateThrottle, ServiceRateThrottle
from api.v2.vendor_router import VendorRouter
from portal.services.dmt_service import DMTService
from portal.utils.logging_helper import get_logger
from .serializers import (
    DMTRegisterSenderSerializer,
    DMTAddBeneficiarySerializer,
    DMTRemitSerializer,
    DMTGetBeneficiariesSerializer,
)

logger = get_logger("api.v2.dmt_views")


class DMTRegisterSenderView(StandardResponseMixin, views.APIView):
    """
    DMT sender/remitter registration.
    POST /api/v2/dmt/register-sender/
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "dmt"
    required_action = "register_sender"

    def post(self, request):
        VendorRouter.get_vendor_for_request(request, "dmt")
        serializer = DMTRegisterSenderSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        service = DMTService()
        if not service.is_available():
            return self.error_response(
                message="DMT service is not configured or enabled",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        data = serializer.validated_data
        result = service.register_sender(
            mobile_number=data["mobile_number"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            pincode=data.get("pincode") or None,
            state=data.get("state") or None,
            address=data.get("address") or None,
            date_of_birth=data.get("date_of_birth") or None,
        )
        if not result.get("success"):
            return self.error_response(
                message=result.get("message", "Sender registration failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        return self.success_response(
            message="Sender registered",
            data={"vendor": result.get("vendor", "paypoint"), "data": result.get("data")},
            request=request,
        )


class DMTAddBeneficiaryView(StandardResponseMixin, views.APIView):
    """
    DMT add beneficiary.
    POST /api/v2/dmt/add-beneficiary/
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "dmt"
    required_action = "add_beneficiary"

    def post(self, request):
        VendorRouter.get_vendor_for_request(request, "dmt")
        serializer = DMTAddBeneficiarySerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        service = DMTService()
        if not service.is_available():
            return self.error_response(
                message="DMT service is not configured or enabled",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        data = serializer.validated_data
        result = service.add_beneficiary(
            sender_mobile=data["sender_mobile"],
            beneficiary_name=data["beneficiary_name"],
            account_number=data["account_number"],
            ifsc=data["ifsc"],
            mobile_number=data.get("mobile_number") or None,
            bank_name=data.get("bank_name") or None,
        )
        if not result.get("success"):
            return self.error_response(
                message=result.get("message", "Add beneficiary failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        return self.success_response(
            message="Beneficiary added",
            data={"vendor": result.get("vendor", "paypoint"), "data": result.get("data")},
            request=request,
        )


class DMTRemitView(StandardResponseMixin, views.APIView):
    """
    DMT remit (money transfer).
    POST /api/v2/dmt/remit/
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "dmt"
    required_action = "remit"

    def post(self, request):
        serializer = DMTRemitSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        service = DMTService()
        if not service.is_available():
            return self.error_response(
                message="DMT service is not configured or enabled",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        data = serializer.validated_data
        result = service.remit(
            sender_mobile=data["sender_mobile"],
            beneficiary_id=data["beneficiary_id"],
            amount=data["amount"],
            client_ref_id=data.get("client_ref_id") or None,
            remarks=data.get("remarks") or None,
        )
        if not result.get("success"):
            return self.error_response(
                message=result.get("message", "Remit failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        return self.success_response(
            message="Remit initiated",
            data={"vendor": result.get("vendor", "paypoint"), "data": result.get("data")},
            request=request,
        )


class DMTTransactionStatusView(StandardResponseMixin, views.APIView):
    """
    DMT transaction status by reference id.
    GET /api/v2/dmt/status/<ref_id>/
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "dmt"
    required_action = "transaction_status"

    def get(self, request, ref_id):
        service = DMTService()
        if not service.is_available():
            return self.error_response(
                message="DMT service is not configured or enabled",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        result = service.transaction_status(ref_id=ref_id)
        if not result.get("success"):
            return self.error_response(
                message=result.get("message", "Transaction status failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        return self.success_response(
            message="Transaction status",
            data={"vendor": result.get("vendor", "paypoint"), "data": result.get("data")},
            request=request,
        )


class DMTGetBeneficiariesView(StandardResponseMixin, views.APIView):
    """
    DMT get beneficiaries for a sender.
    POST /api/v2/dmt/beneficiaries/
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "dmt"
    required_action = "get_beneficiaries"

    def post(self, request):
        serializer = DMTGetBeneficiariesSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        service = DMTService()
        if not service.is_available():
            return self.error_response(
                message="DMT service is not configured or enabled",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        data = serializer.validated_data
        result = service.get_beneficiaries(sender_mobile=data["sender_mobile"])
        if not result.get("success"):
            return self.error_response(
                message=result.get("message", "Get beneficiaries failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        return self.success_response(
            message="Beneficiaries",
            data={"vendor": result.get("vendor", "paypoint"), "data": result.get("data")},
            request=request,
        )
