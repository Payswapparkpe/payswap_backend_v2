"""
AEPS (Aadhaar Enabled Payment System) APIs for External Partners (API v2)
Uses PayPoint as AEPS vendor. All endpoints require API key and aeps service permission.
"""
from rest_framework import views, status
from rest_framework.parsers import JSONParser

from api.mixins.response_mixin import StandardResponseMixin
from api.v2.authentication import APIKeyAuthentication
from api.v2.permissions import HasAPIKey, HasServicePermission, HasVendorAccess
from api.v2.throttling import APIKeyRateThrottle, ServiceRateThrottle
from api.v2.vendor_router import VendorRouter
from portal.services.aeps_service import AEPSService
from portal.utils.logging_helper import get_logger
from .serializers import (
    AEPSBalanceEnquirySerializer,
    AEPSCashWithdrawalSerializer,
    AEPSMiniStatementSerializer,
    AEPSAgentRegistrationSerializer,
    AEPSUpdateAgentDetailsSerializer,
    AEPSAgentServiceStatusSerializer,
    AEPSAgentAuthenticationSerializer,
    AEPSTwoFactorAuthenticationSerializer,
)

logger = get_logger("api.v2.aeps_views")


class AEPSBalanceEnquiryView(StandardResponseMixin, views.APIView):
    """
    AEPS balance enquiry. Vendor from partner assignment (e.g. PayPoint).
    POST /api/v2/aeps/balance/
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "aeps"
    required_action = "balance_enquiry"

    def post(self, request):
        VendorRouter.get_vendor_for_request(request, "aeps")
        serializer = AEPSBalanceEnquirySerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        service = AEPSService()
        if not service.is_available():
            return self.error_response(
                message="AEPS service is not configured or enabled",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        data = serializer.validated_data
        result = service.balance_enquiry(
            aadhaar_number=data["aadhaar_number"],
            mobile_number=data["mobile_number"],
            bank_iin=data["bank_iin"],
            rd_request=data["rd_request"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            terminal_id=data.get("terminal_id") or None,
        )
        if not result.get("success"):
            return self.error_response(
                message=result.get("message", "Balance enquiry failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        return self.success_response(
            message="Balance enquiry successful",
            data={
                "balance": result.get("balance"),
                "rrn": result.get("rrn"),
                "vendor": result.get("vendor", "paypoint"),
                "data": result.get("data"),
            },
            request=request,
        )


class AEPSCashWithdrawalView(StandardResponseMixin, views.APIView):
    """
    AEPS cash withdrawal.
    POST /api/v2/aeps/withdrawal/
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "aeps"
    required_action = "cash_withdrawal"

    def post(self, request):
        VendorRouter.get_vendor_for_request(request, "aeps")
        serializer = AEPSCashWithdrawalSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        service = AEPSService()
        if not service.is_available():
            return self.error_response(
                message="AEPS service is not configured or enabled",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        data = serializer.validated_data
        result = service.cash_withdrawal(
            aadhaar_number=data["aadhaar_number"],
            mobile_number=data["mobile_number"],
            bank_iin=data["bank_iin"],
            rd_request=data["rd_request"],
            amount=str(data["amount"]),
            latitude=data["latitude"],
            longitude=data["longitude"],
            terminal_id=data.get("terminal_id") or None,
            client_ref_id=data.get("client_ref_id") or None,
        )
        if not result.get("success"):
            return self.error_response(
                message=result.get("message", "Cash withdrawal failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        return self.success_response(
            message="Cash withdrawal submitted",
            data={
                "transaction_id": result.get("transaction_id"),
                "rrn": result.get("rrn"),
                "status": result.get("status"),
                "vendor": result.get("vendor", "paypoint"),
                "data": result.get("data"),
            },
            request=request,
        )


class AEPSMiniStatementView(StandardResponseMixin, views.APIView):
    """
    AEPS mini statement.
    POST /api/v2/aeps/mini-statement/
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "aeps"
    required_action = "mini_statement"

    def post(self, request):
        VendorRouter.get_vendor_for_request(request, "aeps")
        serializer = AEPSMiniStatementSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        service = AEPSService()
        if not service.is_available():
            return self.error_response(
                message="AEPS service is not configured or enabled",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        data = serializer.validated_data
        result = service.mini_statement(
            aadhaar_number=data["aadhaar_number"],
            mobile_number=data["mobile_number"],
            bank_iin=data["bank_iin"],
            rd_request=data["rd_request"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            terminal_id=data.get("terminal_id") or None,
        )
        if not result.get("success"):
            return self.error_response(
                message=result.get("message", "Mini statement failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        return self.success_response(
            message="Mini statement fetched",
            data={
                "transactions": result.get("transactions", []),
                "vendor": result.get("vendor", "paypoint"),
                "data": result.get("data"),
            },
            request=request,
        )


class AEPSTransactionStatusView(StandardResponseMixin, views.APIView):
    """
    Get AEPS transaction status by ref_id.
    GET /api/v2/aeps/status/<ref_id>/
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "aeps"
    required_action = "transaction_status"

    def get(self, request, ref_id):
        VendorRouter.get_vendor_for_request(request, "aeps")
        service = AEPSService()
        if not service.is_available():
            return self.error_response(
                message="AEPS service is not configured or enabled",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        result = service.transaction_status(ref_id=ref_id)
        if not result.get("success"):
            return self.error_response(
                message=result.get("message", "Status fetch failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        return self.success_response(
            message="Status fetched",
            data={
                "ref_id": ref_id,
                "status": result.get("status"),
                "data": result.get("data"),
            },
            request=request,
        )


class AEPSAgentRegistrationView(StandardResponseMixin, views.APIView):
    """
    PayPoint AEPS Agent Registration.
    POST /api/v2/aeps/agent-registration/
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "aeps"
    required_action = "agent_registration"

    def post(self, request):
        VendorRouter.get_vendor_for_request(request, "aeps")
        serializer = AEPSAgentRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        service = AEPSService()
        if not service.is_available():
            return self.error_response(
                message="AEPS service is not configured or enabled",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        data = serializer.validated_data
        result = service.agent_registration(
            agent_name=data.get("agent_name") or None,
            mobile_number=data.get("mobile_number") or None,
            email=data.get("email") or None,
        )
        if not result.get("success"):
            return self.error_response(
                message=result.get("message", "Agent registration failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        return self.success_response(
            message="Agent registration successful",
            data=result.get("data", {}),
            request=request,
        )


class AEPSUpdateAgentDetailsView(StandardResponseMixin, views.APIView):
    """
    PayPoint AEPS Update Agent Details.
    POST /api/v2/aeps/update-agent-details/
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "aeps"
    required_action = "update_agent_details"

    def post(self, request):
        VendorRouter.get_vendor_for_request(request, "aeps")
        serializer = AEPSUpdateAgentDetailsSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        service = AEPSService()
        if not service.is_available():
            return self.error_response(
                message="AEPS service is not configured or enabled",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        data = serializer.validated_data
        result = service.update_agent_details(
            agent_id=data["agent_id"],
            agent_name=data.get("agent_name") or None,
            mobile_number=data.get("mobile_number") or None,
            email=data.get("email") or None,
        )
        if not result.get("success"):
            return self.error_response(
                message=result.get("message", "Update agent failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        return self.success_response(
            message="Agent details updated",
            data=result.get("data", {}),
            request=request,
        )


class AEPSAgentServiceStatusView(StandardResponseMixin, views.APIView):
    """
    PayPoint AEPS Check Agent Service Status.
    POST /api/v2/aeps/agent-service-status/
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "aeps"
    required_action = "agent_service_status"

    def post(self, request):
        VendorRouter.get_vendor_for_request(request, "aeps")
        serializer = AEPSAgentServiceStatusSerializer(data=request.data or {})
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        service = AEPSService()
        if not service.is_available():
            return self.error_response(
                message="AEPS service is not configured or enabled",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        data = serializer.validated_data
        result = service.check_agent_service_status(agent_id=(data.get("agent_id") or "").strip() or None)
        if not result.get("success"):
            return self.error_response(
                message=result.get("message", "Check agent service status failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        return self.success_response(
            message="Agent service status fetched",
            data=result.get("data", {}),
            request=request,
        )


class AEPSAgentAuthenticationView(StandardResponseMixin, views.APIView):
    """
    PayPoint AEPS Check Agent Authentication.
    POST /api/v2/aeps/agent-authentication/
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "aeps"
    required_action = "agent_authentication"

    def post(self, request):
        VendorRouter.get_vendor_for_request(request, "aeps")
        serializer = AEPSAgentAuthenticationSerializer(data=request.data or {})
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        service = AEPSService()
        if not service.is_available():
            return self.error_response(
                message="AEPS service is not configured or enabled",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        data = serializer.validated_data
        result = service.check_agent_authentication(agent_id=(data.get("agent_id") or "").strip() or None)
        if not result.get("success"):
            return self.error_response(
                message=result.get("message", "Agent authentication check failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        return self.success_response(
            message="Agent authentication check successful",
            data=result.get("data", {}),
            request=request,
        )


class AEPSTwoFactorAuthenticationView(StandardResponseMixin, views.APIView):
    """
    PayPoint AEPS Two Factor Authentication.
    POST /api/v2/aeps/two-factor-auth/
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "aeps"
    required_action = "two_factor_authentication"

    def post(self, request):
        VendorRouter.get_vendor_for_request(request, "aeps")
        serializer = AEPSTwoFactorAuthenticationSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request,
            )
        service = AEPSService()
        if not service.is_available():
            return self.error_response(
                message="AEPS service is not configured or enabled",
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                request=request,
            )
        data = serializer.validated_data
        result = service.two_factor_authentication(
            otp=data.get("otp") or None,
            mobile_number=data.get("mobile_number") or None,
        )
        if not result.get("success"):
            return self.error_response(
                message=result.get("message", "Two factor authentication failed"),
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        return self.success_response(
            message="Two factor authentication successful",
            data=result.get("data", {}),
            request=request,
        )
