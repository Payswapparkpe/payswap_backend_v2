"""
KYC/Verification APIs for External Partners (API v2)
All endpoints require API key authentication with service-level permissions
"""
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import Q
from io import BytesIO

from api.mixins.response_mixin import StandardResponseMixin
from api.v2.authentication import APIKeyAuthentication
from api.v2.permissions import HasAPIKey, HasServicePermission, HasVendorAccess
from api.v2.throttling import APIKeyRateThrottle, ServiceRateThrottle
from api.v2.vendor_router import VendorRouter
from portal.services.verification_api import VerificationAPIService
from portal.utils.logging_helper import get_logger
from .serializers import (
    PANVerifySerializer, AadhaarVerifySerializer, BankVerifySerializer,
    DrivingLicenseVerifySerializer, VoterIDVerifySerializer,
    PassportVerifySerializer, GSTVerifySerializer,
    FaceMatchSerializer, FaceLivenessSerializer,
    VerificationStatusSerializer
)

logger = get_logger('api.v2.kyc_views')


class PANVerifyView(StandardResponseMixin, views.APIView):
    """
    PAN verification
    POST /api/v2/kyc/pan/verify/
    
    Requires permission: kyc.pan
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'kyc'
    required_action = 'pan'
    
    def post(self, request):
        """Verify PAN"""
        VendorRouter.get_vendor_for_request(request, 'kyc')
        serializer = PANVerifySerializer(data=request.data)
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
            
            verification_service = VerificationAPIService()
            result = verification_service.verify_pan(
                pan_number=serializer.validated_data['pan_number'],
                metadata={
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            # Charge partner for service usage
            from portal.services.partner_accounting_service import PartnerAccountingService
            from portal.models import Service, ResellerPartnerPricing
            from decimal import Decimal
            
            try:
                # Get KYC service
                kyc_service_obj = Service.objects.filter(
                    Q(code='KYC') | Q(code='VERIFICATION') | Q(name__icontains='kyc') | Q(name__icontains='verification')
                ).filter(status='active').first()
                
                if kyc_service_obj:
                    accounting_service = PartnerAccountingService()
                    # Get partner pricing to calculate charge amount
                    try:
                        pricing = ResellerPartnerPricing.objects.get(
                            partner=partner,
                            service=kyc_service_obj,
                            is_active=True
                        )
                        # For KYC, use base price or fixed cost
                        charge_amount = pricing.base_price if pricing.base_price > 0 else Decimal('1.00')
                    except:
                        # If no pricing found, use default cost
                        charge_amount = Decimal('1.00')
                    
                    # Charge partner wallet
                    transaction, success = accounting_service.charge_partner_for_service(
                        partner=partner,
                        service=kyc_service_obj,
                        amount=charge_amount,
                        api_key=api_key,
                        reference_id=result.get('verification_id', f'PAN_{serializer.validated_data["pan_number"]}'),
                        description=f'PAN verification: {serializer.validated_data["pan_number"]}',
                        metadata={
                            'verification_id': result.get('verification_id'),
                            'pan_number': serializer.validated_data['pan_number']
                        }
                    )
                    
                    if not success:
                        # Insufficient balance - return error
                        return self.error_response(
                            message="Insufficient wallet balance",
                            status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            request=request
                        )
            except Exception as e:
                logger.error(f'Error charging partner for KYC service: {str(e)}', exc_info=True)
                # Don't fail the request if transaction recording fails
            
            return self.success_response(
                message="PAN verification completed",
                data=result,
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error verifying PAN via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to verify PAN",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class AadhaarVerifyView(StandardResponseMixin, views.APIView):
    """
    Aadhaar verification
    POST /api/v2/kyc/aadhaar/verify/
    
    Requires permission: kyc.aadhaar
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'kyc'
    required_action = 'aadhaar'
    
    def post(self, request):
        """Verify Aadhaar"""
        VendorRouter.get_vendor_for_request(request, 'kyc')
        serializer = AadhaarVerifySerializer(data=request.data)
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
            
            verification_service = VerificationAPIService()
            result = verification_service.verify_aadhaar(
                aadhaar_number=serializer.validated_data['aadhaar_number'],
                metadata={
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            return self.success_response(
                message="Aadhaar verification completed",
                data=result,
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error verifying Aadhaar via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to verify Aadhaar",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class BankVerifyView(StandardResponseMixin, views.APIView):
    """
    Bank account verification
    POST /api/v2/kyc/bank/verify/
    
    Requires permission: kyc.bank
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'kyc'
    required_action = 'bank'
    
    def post(self, request):
        """Verify bank account"""
        VendorRouter.get_vendor_for_request(request, 'kyc')
        serializer = BankVerifySerializer(data=request.data)
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
            
            verification_service = VerificationAPIService()
            result = verification_service.verify_bank_account(
                account_number=serializer.validated_data['account_number'],
                ifsc_code=serializer.validated_data['ifsc_code'],
                account_holder_name=serializer.validated_data.get('account_holder_name'),
                metadata={
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            return self.success_response(
                message="Bank account verification completed",
                data=result,
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error verifying bank account via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to verify bank account",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class DrivingLicenseVerifyView(StandardResponseMixin, views.APIView):
    """
    Driving license verification
    POST /api/v2/kyc/driving-license/verify/
    
    Requires permission: kyc.driving_license
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser, MultiPartParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'kyc'
    required_action = 'driving_license'
    
    def post(self, request):
        """Verify driving license"""
        VendorRouter.get_vendor_for_request(request, 'kyc')
        serializer = DrivingLicenseVerifySerializer(data=request.data)
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
            
            verification_service = VerificationAPIService()
            
            # Handle file upload if provided
            document_file = request.FILES.get('document')
            document_base64 = serializer.validated_data.get('document_base64')
            
            result = verification_service.verify_driving_license(
                dl_number=serializer.validated_data['dl_number'],
                dob=serializer.validated_data.get('dob'),
                document_file=document_file,
                document_base64=document_base64,
                metadata={
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            return self.success_response(
                message="Driving license verification completed",
                data=result,
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error verifying driving license via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to verify driving license",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class VoterIDVerifyView(StandardResponseMixin, views.APIView):
    """
    Voter ID verification
    POST /api/v2/kyc/voter-id/verify/
    
    Requires permission: kyc.voter_id
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser, MultiPartParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'kyc'
    required_action = 'voter_id'
    
    def post(self, request):
        """Verify voter ID"""
        VendorRouter.get_vendor_for_request(request, 'kyc')
        serializer = VoterIDVerifySerializer(data=request.data)
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
            
            verification_service = VerificationAPIService()
            
            document_file = request.FILES.get('document')
            document_base64 = serializer.validated_data.get('document_base64')
            
            result = verification_service.verify_voter_id(
                voter_id_number=serializer.validated_data['voter_id_number'],
                document_file=document_file,
                document_base64=document_base64,
                metadata={
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            return self.success_response(
                message="Voter ID verification completed",
                data=result,
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error verifying voter ID via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to verify voter ID",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class PassportVerifyView(StandardResponseMixin, views.APIView):
    """
    Passport verification
    POST /api/v2/kyc/passport/verify/
    
    Requires permission: kyc.passport
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser, MultiPartParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'kyc'
    required_action = 'passport'
    
    def post(self, request):
        """Verify passport"""
        VendorRouter.get_vendor_for_request(request, 'kyc')
        serializer = PassportVerifySerializer(data=request.data)
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
            
            verification_service = VerificationAPIService()
            
            document_file = request.FILES.get('document')
            document_base64 = serializer.validated_data.get('document_base64')
            
            result = verification_service.verify_passport(
                passport_number=serializer.validated_data['passport_number'],
                document_file=document_file,
                document_base64=document_base64,
                metadata={
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            return self.success_response(
                message="Passport verification completed",
                data=result,
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error verifying passport via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to verify passport",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class GSTVerifyView(StandardResponseMixin, views.APIView):
    """
    GST verification
    POST /api/v2/kyc/gst/verify/
    
    Requires permission: kyc.gst
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'kyc'
    required_action = 'gst'
    
    def post(self, request):
        """Verify GST"""
        VendorRouter.get_vendor_for_request(request, 'kyc')
        serializer = GSTVerifySerializer(data=request.data)
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
            
            verification_service = VerificationAPIService()
            result = verification_service.verify_gst(
                gst_number=serializer.validated_data['gst_number'],
                metadata={
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            return self.success_response(
                message="GST verification completed",
                data=result,
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error verifying GST via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to verify GST",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class FaceMatchView(StandardResponseMixin, views.APIView):
    """
    Face matching
    POST /api/v2/kyc/face-match/
    
    Requires permission: kyc.face_match
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser, MultiPartParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'kyc'
    required_action = 'face_match'
    
    def post(self, request):
        """Match faces"""
        VendorRouter.get_vendor_for_request(request, 'kyc')
        serializer = FaceMatchSerializer(data=request.data)
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
            
            verification_service = VerificationAPIService()
            
            image1_file = request.FILES.get('image1')
            image2_file = request.FILES.get('image2')
            image1_base64 = serializer.validated_data.get('image1_base64')
            image2_base64 = serializer.validated_data.get('image2_base64')
            
            result = verification_service.face_match(
                image1_file=image1_file,
                image2_file=image2_file,
                image1_base64=image1_base64,
                image2_base64=image2_base64,
                metadata={
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            return self.success_response(
                message="Face matching completed",
                data=result,
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error matching faces via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to match faces",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class FaceLivenessView(StandardResponseMixin, views.APIView):
    """
    Face liveness check
    POST /api/v2/kyc/face-liveness/
    
    Requires permission: kyc.face_liveness
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission, HasVendorAccess]
    parser_classes = [JSONParser, MultiPartParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'kyc'
    required_action = 'face_liveness'
    
    def post(self, request):
        """Check face liveness"""
        VendorRouter.get_vendor_for_request(request, 'kyc')
        serializer = FaceLivenessSerializer(data=request.data)
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
            
            verification_service = VerificationAPIService()
            
            image_file = request.FILES.get('image')
            image_base64 = serializer.validated_data.get('image_base64')
            
            result = verification_service.face_liveness(
                image_file=image_file,
                image_base64=image_base64,
                metadata={
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            return self.success_response(
                message="Face liveness check completed",
                data=result,
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error checking face liveness via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to check face liveness",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class VerificationStatusView(StandardResponseMixin, views.APIView):
    """
    Get verification status
    GET /api/v2/kyc/verifications/{verification_id}/
    
    Requires permission: kyc.status (or any kyc permission)
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasVendorAccess]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    service_name = 'kyc'

    def get(self, request, verification_id):
        """Get verification status"""
        VendorRouter.get_vendor_for_request(request, 'kyc')
        try:
            partner = request.partner
            api_key = request.api_key
            
            verification_service = VerificationAPIService()
            result = verification_service.get_verification_status(
                verification_id=verification_id,
                metadata={
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            return self.success_response(
                message="Verification status retrieved",
                data=result,
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error getting verification status via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to get verification status",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )
