"""
SMS/OTP APIs for External Partners (API v2)
All endpoints require API key authentication with service-level permissions
"""
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.parsers import JSONParser

from api.mixins.response_mixin import StandardResponseMixin
from api.v2.authentication import APIKeyAuthentication
from api.v2.permissions import HasAPIKey, HasServicePermission, HasVendorAccess
from api.v2.throttling import APIKeyRateThrottle, ServiceRateThrottle
from api.v2.vendor_router import VendorRouter
from portal.services.notification_service_v2 import NotificationServiceV2
from portal.services.otp_service import OTPService
from portal.utils.logging_helper import get_logger
from .serializers import (
    SMSSendSerializer, SMSOTPSendSerializer, SMSOTPVerifySerializer,
    SMSDeliveryStatusSerializer
)

logger = get_logger('api.v2.sms_views')


class SMSSendView(StandardResponseMixin, views.APIView):
    """
    Send SMS
    POST /api/v2/sms/send/
    
    Requires permission: sms.send
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'sms'
    required_action = 'send'
    
    def post(self, request):
        """Send SMS"""
        VendorRouter.get_vendor_for_request(request, 'sms')
        serializer = SMSSendSerializer(data=request.data)
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
            
            phone_number = serializer.validated_data['phone_number']
            message = serializer.validated_data['message']
            
            # Send SMS
            notification_service = NotificationServiceV2()
            result = notification_service.send_sms(
                phone_number=phone_number,
                message=message,
                user_id=None,
                context={
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                },
                async_send=True
            )
            
            if result.get('success'):
                return self.success_response(
                    message="SMS sent successfully",
                    data={
                        'phone_number': phone_number[-4:].rjust(len(phone_number), '*'),  # Masked
                        'message_sent': True,
                        'task_id': result.get('task_id'),
                        'message_id': result.get('message_id')
                    },
                    request=request
                )
            else:
                return self.error_response(
                    message=result.get('message', 'Failed to send SMS'),
                    status_code=status.HTTP_400_BAD_REQUEST,
                    request=request
                )
            
        except Exception as e:
            logger.error(f'Error sending SMS via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to send SMS",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class SMSOTPSendView(StandardResponseMixin, views.APIView):
    """
    Send OTP
    POST /api/v2/sms/otp/send/
    
    Requires permission: sms.otp_send
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'sms'
    required_action = 'otp_send'
    
    def post(self, request):
        """Send OTP"""
        VendorRouter.get_vendor_for_request(request, 'sms')
        serializer = SMSOTPSendSerializer(data=request.data)
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
            
            phone_number = serializer.validated_data['phone_number']
            
            # Send OTP
            notification_service = NotificationServiceV2()
            result = notification_service.send_otp(
                phone_number=phone_number,
                otp_code=None,  # Will be generated
                user_id=None,
                async_send=True
            )
            
            # Note: OTP code is not returned for security
            return self.success_response(
                message="OTP sent successfully",
                data={
                    'phone_number': phone_number[-4:].rjust(len(phone_number), '*'),  # Masked
                    'otp_sent': True,
                    'task_id': result.get('task_id')
                },
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error sending OTP via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to send OTP",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class SMSOTPVerifyView(StandardResponseMixin, views.APIView):
    """
    Verify OTP
    POST /api/v2/sms/otp/verify/
    
    Requires permission: sms.otp_verify
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'sms'
    required_action = 'otp_verify'
    
    def post(self, request):
        """Verify OTP"""
        VendorRouter.get_vendor_for_request(request, 'sms')
        serializer = SMSOTPVerifySerializer(data=request.data)
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
            
            phone_number = serializer.validated_data['phone_number']
            otp_code = serializer.validated_data['otp_code']
            
            # Verify OTP
            otp_service = OTPService()
            verified, _ = otp_service.verify_otp(phone_number, otp_code)
            
            if verified:
                return self.success_response(
                    message="OTP verified successfully",
                    data={
                        'verified': True,
                        'phone_number': phone_number[-4:].rjust(len(phone_number), '*')  # Masked
                    },
                    request=request
                )
            else:
                return self.error_response(
                    message="Invalid or expired OTP",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    request=request
                )
            
        except Exception as e:
            logger.error(f'Error verifying OTP via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to verify OTP",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class SMSDeliveryStatusView(StandardResponseMixin, views.APIView):
    """
    Check SMS delivery status
    GET /api/v2/sms/delivery-status/{message_id}/
    
    Requires permission: sms.delivery_status
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'sms'
    required_action = 'delivery_status'
    
    def get(self, request, message_id):
        """Get delivery status"""
        VendorRouter.get_vendor_for_request(request, 'sms')
        try:
            partner = request.partner
            api_key = request.api_key
            
            # TODO: Implement delivery status check from SMS provider
            data = {
                'message_id': message_id,
                'status': 'DELIVERED',  # DELIVERED, PENDING, FAILED
                'delivered_at': None
            }
            from django.conf import settings
            if getattr(settings, 'V2_PLACEHOLDER_MODE', True):
                data['mode'] = 'placeholder'
            return self.success_response(
                message="Delivery status retrieved",
                data=data,
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error getting delivery status via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to get delivery status",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )
