"""
Instantpay module APIs for external partners (API v2).
"""
from __future__ import annotations

from rest_framework import status, views
from rest_framework.parsers import JSONParser

from api.mixins.response_mixin import StandardResponseMixin
from api.v2.authentication import APIKeyAuthentication
from api.v2.permissions import HasAPIKey, HasServicePermission, HasVendorAccess
from api.v2.throttling import APIKeyRateThrottle, ServiceRateThrottle
from api.v2.vendor_router import VendorRouter
from portal.services.instantpay_hub_service import InstantpayHubService
from .instantpay_serializers import (
    AepsBalanceSerializer,
    AepsWithdrawSerializer,
    BinLookupSerializer,
    CreditCardBillPaySerializer,
    CreditReportSerializer,
    CreditScoreSimulatorSerializer,
    DigiLockerInitSerializer,
    DmtTransferSerializer,
    GenericVehicleSerializer,
    MerchantOnboardingSerializer,
)


class InstantpayBaseView(StandardResponseMixin, views.APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]

    service_name = None
    required_action = None
    api_code = None
    serializer_class = None
    requires_idempotency = False

    def post(self, request):
        VendorRouter.get_vendor_for_request(request, self.service_name)
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return self.error_response("Invalid request data", serializer.errors, status.HTTP_400_BAD_REQUEST, request)

        service = InstantpayHubService()
        if not service.is_available():
            return self.error_response("Instantpay service is not configured", status_code=status.HTTP_503_SERVICE_UNAVAILABLE, request=request)

        partner = getattr(request, "partner", None)
        idempotency_key = request.headers.get("Idempotency-Key")
        if self.requires_idempotency and not idempotency_key:
            return self.error_response(
                "Idempotency-Key header is required",
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request,
            )

        result = service.execute(
            self.api_code,
            serializer.validated_data,
            partner_id=getattr(partner, "id", None),
            partner_code=getattr(partner, "partner_code", None),
            idempotency_key=idempotency_key,
        )
        if not result.get("success"):
            return self.error_response(
                message=result.get("message") or "Instantpay vendor call failed",
                errors=[{"error": result.get("error"), "vendor_status": result.get("vendor_status")}],
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        return self.success_response("Request processed", result, request=request)


class AepsWithdrawView(InstantpayBaseView):
    service_name = "aeps"
    required_action = "withdraw"
    api_code = "aeps_withdraw"
    serializer_class = AepsWithdrawSerializer
    requires_idempotency = True


class AepsBalanceCheckView(InstantpayBaseView):
    service_name = "aeps"
    required_action = "balance_check"
    api_code = "balance_check"
    serializer_class = AepsBalanceSerializer


class AepsAccountStatementView(InstantpayBaseView):
    service_name = "aeps"
    required_action = "account_statement"
    api_code = "account_statement"
    serializer_class = AepsBalanceSerializer


class DmtTransferView(InstantpayBaseView):
    service_name = "dmt"
    required_action = "transfer"
    api_code = "dmt_transfer"
    serializer_class = DmtTransferSerializer
    requires_idempotency = True


class DomesticRemittanceView(InstantpayBaseView):
    service_name = "dmt"
    required_action = "remittance_domestic"
    api_code = "remittance_domestic"
    serializer_class = DmtTransferSerializer
    requires_idempotency = True


class NepalRemittanceView(InstantpayBaseView):
    service_name = "dmt"
    required_action = "remittance_nepal"
    api_code = "remittance_nepal"
    serializer_class = DmtTransferSerializer
    requires_idempotency = True


class CreditCardBillPayView(InstantpayBaseView):
    service_name = "billpay"
    required_action = "credit_card_pay"
    api_code = "credit_card_bill_pay"
    serializer_class = CreditCardBillPaySerializer
    requires_idempotency = True


class RcVerificationView(InstantpayBaseView):
    service_name = "vehicle"
    required_action = "rc_verify"
    api_code = "rc_verification"
    serializer_class = GenericVehicleSerializer


class VehicleChallanLookupView(InstantpayBaseView):
    service_name = "vehicle"
    required_action = "challan_lookup"
    api_code = "vehicle_challan_lookup"
    serializer_class = GenericVehicleSerializer


class DigiLockerInitView(InstantpayBaseView):
    service_name = "identity_docs"
    required_action = "digilocker_init"
    api_code = "digilocker_init"
    serializer_class = DigiLockerInitSerializer


class BinLookupView(InstantpayBaseView):
    service_name = "cards"
    required_action = "bin_lookup"
    api_code = "card_bin_lookup"
    serializer_class = BinLookupSerializer


class CreditReportView(InstantpayBaseView):
    service_name = "credit"
    required_action = "report"
    api_code = "credit_report"
    serializer_class = CreditReportSerializer


class CreditScoreSimulatorView(InstantpayBaseView):
    service_name = "credit"
    required_action = "score_simulator"
    api_code = "credit_score_simulator"
    serializer_class = CreditScoreSimulatorSerializer


class MerchantOnboardingView(InstantpayBaseView):
    service_name = "merchant"
    required_action = "onboarding"
    api_code = "merchant_onboarding"
    serializer_class = MerchantOnboardingSerializer
    requires_idempotency = True


class TransactionStatusView(StandardResponseMixin, views.APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = "reconciliation"
    required_action = "transaction_status"

    def get(self, request, partner_txn_id: str):
        VendorRouter.get_vendor_for_request(request, self.service_name)
        service = InstantpayHubService()
        if not service.is_available():
            return self.error_response("Instantpay service is not configured", status_code=status.HTTP_503_SERVICE_UNAVAILABLE, request=request)
        partner = getattr(request, "partner", None)
        result = service.get_status(partner_txn_id, partner_id=getattr(partner, "id", None))
        if not result.get("success"):
            result = service.execute("transaction_status", {"partner_txn_id": partner_txn_id})
        if not result.get("success"):
            return self.error_response(
                message=result.get("message") or "Status fetch failed",
                errors=[{"error": result.get("error")}],
                status_code=status.HTTP_502_BAD_GATEWAY,
                request=request,
            )
        return self.success_response("Status fetched", result, request=request)
