"""
Payment Gateway APIs for External Partners (API v2)
All endpoints require API key authentication with service-level permissions
"""
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from django_filters.rest_framework import DjangoFilterBackend

from api.mixins.response_mixin import StandardResponseMixin
from api.v2.authentication import APIKeyAuthentication
from api.v2.permissions import HasAPIKey, HasServicePermission, HasVendorAccess
from api.v2.throttling import APIKeyRateThrottle, ServiceRateThrottle
from api.v2.vendor_router import VendorRouter
from django.utils import timezone
from portal.utils.logging_helper import get_logger
from .serializers import (
    PaymentInitiateSerializer, PaymentStatusSerializer,
    PaymentRefundSerializer, PaymentListSerializer
)

logger = get_logger('api.v2.payment_views')

def _api_prefix_from_request(request) -> str:
    """
    Return API prefix based on request path.
    Allows reusing v2 views under /api/v1/ without hardcoding.
    """
    path = (getattr(request, "path", "") or "").strip()
    if path.startswith("/api/v2/"):
        return "/api/v2"
    if path.startswith("/api/v1/"):
        return "/api/v1"
    return "/api/v2"


class PaymentInitiateView(StandardResponseMixin, views.APIView):
    """
    Initiate payment
    POST /api/v2/payments/initiate/
    
    Requires permission: payment.initiate
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'payment'
    required_action = 'initiate'
    
    def post(self, request):
        """Initiate payment"""
        VendorRouter.get_vendor_for_request(request, 'payment')
        serializer = PaymentInitiateSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        
        try:
            partner = request.partner
            api_key = request.api_key
            
            # TODO: Implement payment initiation using Cashfree PG or other gateway
            # For now, return placeholder response
            payment_data = serializer.validated_data
            
            # Placeholder - implement actual payment gateway integration
            payment_id = f"PAY_{partner.partner_code}_{timezone.now().timestamp()}"
            
            return self.success_response(
                message="Payment initiated successfully",
                data={
                    'payment_id': payment_id,
                    'amount': str(payment_data.get('amount', '')),
                    'currency': payment_data.get('currency', 'INR'),
                    'status': 'PENDING',
                    'payment_url': f'/payment/{payment_id}/',  # Placeholder
                    'status_url': f'{_api_prefix_from_request(request)}/payments/{payment_id}/status/'
                },
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error initiating payment via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to initiate payment",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class PaymentStatusView(StandardResponseMixin, views.APIView):
    """
    Check payment status
    GET /api/v2/payments/{payment_id}/status/
    
    Requires permission: payment.status
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'payment'
    required_action = 'status'
    
    def get(self, request, payment_id):
        """Get payment status"""
        VendorRouter.get_vendor_for_request(request, 'payment')
        try:
            partner = request.partner
            api_key = request.api_key
            
            # TODO: Implement payment status check
            # Placeholder response
            return self.success_response(
                message="Payment status retrieved",
                data={
                    'payment_id': payment_id,
                    'status': 'PENDING',  # SUCCESS, FAILED, PENDING
                    'amount': '0.00',
                    'currency': 'INR'
                },
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error getting payment status via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to get payment status",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class PaymentRefundView(StandardResponseMixin, views.APIView):
    """
    Refund payment
    POST /api/v2/payments/{payment_id}/refund/
    
    Requires permission: payment.refund
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'payment'
    required_action = 'refund'
    
    def post(self, request, payment_id):
        """Refund payment"""
        VendorRouter.get_vendor_for_request(request, 'payment')
        serializer = PaymentRefundSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        
        try:
            partner = request.partner
            api_key = request.api_key
            
            # TODO: Implement payment refund
            refund_amount = serializer.validated_data.get('amount')
            
            return self.success_response(
                message="Refund initiated successfully",
                data={
                    'payment_id': payment_id,
                    'refund_id': f"REF_{payment_id}",
                    'amount': str(refund_amount) if refund_amount else 'Full',
                    'status': 'PENDING'
                },
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error refunding payment via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to refund payment",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class PaymentListView(StandardResponseMixin, views.APIView):
    """
    List payments
    GET /api/v2/payments/
    
    Requires permission: payment.status
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'payment'
    required_action = 'status'
    
    def get(self, request):
        """List payments for this partner"""
        VendorRouter.get_vendor_for_request(request, 'payment')
        try:
            partner = request.partner
            api_key = request.api_key
            
            # TODO: Implement payment listing with filters
            # Placeholder response
            return self.success_response(
                message="Payments retrieved successfully",
                data={
                    'payments': [],
                    'total': 0,
                    'page': 1,
                    'page_size': 20
                },
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error listing payments via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to retrieve payments",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )
