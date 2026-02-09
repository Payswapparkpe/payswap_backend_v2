"""
Voucher Management APIs for External Partners (API v2)
All endpoints require API key authentication with service-level permissions
"""
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone
from decimal import Decimal
from portal.models import Service

from api.mixins.response_mixin import StandardResponseMixin
from api.v2.authentication import APIKeyAuthentication
from api.v2.permissions import HasAPIKey, HasServicePermission
from api.v2.throttling import APIKeyRateThrottle, ServiceRateThrottle
from api.v2.idempotency_mixin import IdempotencyMixin
from portal.models import (
    GiftVoucher, GiftVoucherTransaction, BulkVoucherIssuanceBatch,
    GiftVoucherBrand, VoucherClient
)
from portal.services.voucher_service import VoucherService
from portal.services.bulk_voucher_service import BulkVoucherService
from portal.utils.voucher_utils import format_voucher_code, unformat_voucher_code
from portal.utils.voucher_logging import log_voucher_operation
from portal.utils.logging_helper import get_logger
from .serializers import (
    VoucherIssueSerializer, VoucherIssueResponseSerializer,
    VoucherRedeemPINSerializer, VoucherRedeemOTPRequestSerializer,
    VoucherRedeemOTPVerifySerializer, VoucherBalanceSerializer,
    VoucherBalanceResponseSerializer, VoucherPINChangeRequestSerializer,
    VoucherPINChangeVerifySerializer, BulkVoucherIssueSerializer,
    BulkVoucherIssueResponseSerializer, VoucherBatchListSerializer,
    VoucherBatchDetailSerializer
)

logger = get_logger('api.v2.voucher_views')

def _api_prefix_from_request(request) -> str:
    """
    Return API prefix based on request path.
    Allows reusing these views under /api/v1/ without hardcoding /api/v2.
    """
    path = (getattr(request, "path", "") or "").strip()
    if path.startswith("/api/v1/"):
        return "/api/v1"
    if path.startswith("/api/v2/"):
        return "/api/v2"
    return "/api/v2"


class VoucherIssueView(IdempotencyMixin, StandardResponseMixin, views.APIView):
    """
    Issue single voucher
    POST /api/v2/vouchers/issue/
    Idempotent: X-Idempotency-Key or idempotency_key in body (24h TTL).
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    idempotency_scope_suffix = "v2:voucher_issue"
    service_name = 'voucher'
    required_action = 'issue'
    
    def post(self, request):
        """Issue single voucher"""
        serializer = VoucherIssueSerializer(data=request.data)
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
            
            # Get brand - identify by api_identifier (6-char) or brand_code or brand_id
            api_identifier = (serializer.validated_data.get('api_identifier') or '').strip().upper()
            brand_code = (serializer.validated_data.get('brand_code') or '').strip()
            brand_id = serializer.validated_data.get('brand_id')
            try:
                if api_identifier:
                    brand = GiftVoucherBrand.objects.get(api_identifier=api_identifier)
                elif brand_code:
                    brand = GiftVoucherBrand.objects.get(brand_code__iexact=brand_code)
                else:
                    brand = GiftVoucherBrand.objects.get(id=brand_id)
            except GiftVoucherBrand.DoesNotExist:
                return self.error_response(
                    message="Brand not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    request=request
                )
            
            # Get or create system user for API partner (for tracking)
            from portal.models import User
            api_user, _ = User.objects.get_or_create(
                username=f'API_{partner.partner_code}',
                defaults={
                    'role_code': 'api_partner',
                    'is_active': True
                }
            )
            
            # Issue voucher (email is required for API single voucher issuance)
            voucher_service = VoucherService()
            result = voucher_service.issue_single_voucher(
                brand_id=brand.id,
                amount=serializer.validated_data['amount'],
                mobile_number=serializer.validated_data.get('mobile_number'),
                recipient_email=serializer.validated_data.get('email'),
                metadata={
                    **(serializer.validated_data.get('metadata', {})),
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                },
                created_by=api_user,
                client_id=serializer.validated_data.get('client_id'),
                issued_by=api_user,
                issuer_type='API_PARTNER'
            )
            
            # Charge partner for service usage and record transaction
            from portal.services.partner_accounting_service import PartnerAccountingService
            try:
                # Get voucher service (try multiple possible codes)
                voucher_service_obj = Service.objects.filter(
                    Q(code='VOUCHER') | Q(code='GIFT_VOUCHER') | Q(name__icontains='voucher')
                ).filter(status='active').first()
                
                if voucher_service_obj:
                    accounting_service = PartnerAccountingService()
                    # Get partner pricing to calculate charge amount
                    try:
                        from portal.models import ResellerPartnerPricing
                        pricing = ResellerPartnerPricing.objects.get(
                            partner=partner,
                            service=voucher_service_obj,
                            is_active=True
                        )
                        # Calculate charge amount based on pricing
                        charge_amount = pricing.calculate_price(Decimal(str(result['amount'])))
                    except:
                        # If no pricing found, use voucher amount as charge
                        charge_amount = Decimal(str(result['amount']))
                    
                    # Charge partner wallet
                    transaction, success = accounting_service.charge_partner_for_service(
                        partner=partner,
                        service=voucher_service_obj,
                        amount=charge_amount,
                        api_key=api_key,
                        reference_id=result['reference_number'],
                        description=f'Voucher issued: {result["voucher_code"]}',
                        metadata={
                            'voucher_id': result['voucher_id'],
                            'brand_id': brand.id
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
                logger.error(f'Error charging partner for service: {str(e)}', exc_info=True)
                # Don't fail the request if transaction recording fails, but log it
            
            # Log operation
            log_voucher_operation(
                operation='voucher_issued_api_v2',
                log_level='INFO',
                message=f'Voucher issued via API v2 - Reference: {result["reference_number"]}',
                user_id=None,
                extra_data={
                    'voucher_id': result['voucher_id'],
                    'reference_number': result['reference_number'],
                    'brand_id': brand.id,
                    'amount': str(result['amount']),
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            response_serializer = VoucherIssueResponseSerializer(result)
            return self.success_response(
                message="Voucher issued successfully",
                data=response_serializer.data,
                request=request
            )
            
        except ValueError as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        except Exception as e:
            logger.error(f'Error issuing voucher via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to issue voucher",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class BulkVoucherIssueView(IdempotencyMixin, StandardResponseMixin, views.APIView):
    """
    Bulk voucher issuance
    POST /api/v2/vouchers/bulk-issue/
    Idempotent: X-Idempotency-Key or idempotency_key in body (24h TTL).
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    idempotency_scope_suffix = "v2:voucher_bulk_issue"
    service_name = 'voucher'
    required_action = 'issue'
    
    def post(self, request):
        """Issue multiple vouchers"""
        serializer = BulkVoucherIssueSerializer(data=request.data)
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
            
            # Get brand
            try:
                brand = GiftVoucherBrand.objects.get(id=serializer.validated_data['brand_id'])
            except GiftVoucherBrand.DoesNotExist:
                return self.error_response(
                    message="Brand not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    request=request
                )
            
            # Get or create system user for API partner
            from portal.models import User
            api_user, _ = User.objects.get_or_create(
                username=f'API_{partner.partner_code}',
                defaults={
                    'role_code': 'api_partner',
                    'is_active': True
                }
            )
            
            # Create bulk batch
            bulk_service = BulkVoucherService()
            denominations = serializer.validated_data.get('denominations', {})
            
            batch = bulk_service.create_manual_bulk_batch(
                brand_id=brand.id,
                client_id=serializer.validated_data.get('client_id'),
                denominations=denominations,
                issued_by=api_user,
                issuer_type='API_PARTNER'
            )
            
            # Update batch metadata with partner info
            batch.metadata = batch.metadata or {}
            batch.metadata['partner_id'] = partner.id
            batch.metadata['partner_code'] = partner.partner_code
            batch.metadata['api_key_id'] = api_key.id
            batch.save(update_fields=['metadata'])
            
            # Process batch (will be processed asynchronously)
            from portal.tasks.voucher_tasks import process_bulk_voucher_issuance_task
            import threading
            
            # Process in background thread
            def process_batch_async():
                try:
                    process_bulk_voucher_issuance_task(batch.id)
                except Exception as e:
                    logger.error(f'Error processing batch {batch.id}: {str(e)}')
            
            thread = threading.Thread(target=process_batch_async, daemon=True)
            thread.start()
            
            # Log operation
            log_voucher_operation(
                operation='bulk_voucher_issued_api_v2',
                log_level='INFO',
                message=f'Bulk voucher issuance via API v2 - Batch: {batch.batch_reference}',
                user_id=None,
                extra_data={
                    'batch_id': batch.id,
                    'batch_reference': batch.batch_reference,
                    'total_vouchers': batch.total_vouchers,
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            response_data = {
                'batch_id': batch.id,
                'batch_reference': batch.batch_reference,
                'total_vouchers': batch.total_vouchers,
                'status': batch.status,
                'status_url': f'{_api_prefix_from_request(request)}/vouchers/batches/{batch.id}/'
            }
            
            return self.success_response(
                message="Bulk voucher issuance started",
                data=response_data,
                request=request
            )
            
        except ValueError as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        except Exception as e:
            logger.error(f'Error in bulk voucher issuance via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to start bulk voucher issuance",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class VoucherRedeemPINView(IdempotencyMixin, StandardResponseMixin, views.APIView):
    """
    Redeem voucher using PIN
    POST /api/v2/vouchers/redeem-pin/
    Idempotent: X-Idempotency-Key or idempotency_key in body (24h TTL).
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    idempotency_scope_suffix = "v2:voucher_redeem_pin"
    service_name = 'voucher'
    required_action = 'redeem'
    
    def post(self, request):
        """Redeem voucher with PIN"""
        serializer = VoucherRedeemPINSerializer(data=request.data)
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
            
            voucher_code = unformat_voucher_code(serializer.validated_data['voucher_code'])
            pin = serializer.validated_data['pin']
            redemption_amount = serializer.validated_data.get('amount')
            
            try:
                voucher = GiftVoucher.objects.get(voucher_code=voucher_code)
            except GiftVoucher.DoesNotExist:
                return self.error_response(
                    message="Voucher not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    request=request
                )
            amount_to_redeem = redemption_amount if redemption_amount is not None else voucher.current_balance
            
            voucher_service = VoucherService()
            result = voucher_service.redeem_voucher_pin(
                voucher_code=voucher_code,
                pin=pin,
                amount=amount_to_redeem,
                transaction_ref=serializer.validated_data.get('transaction_ref'),
                ip_address=self.get_client_ip(request),
            )
            amount_redeemed = result.get('redeemed_amount', '')
            remaining = result.get('balance_after', '')
            
            from portal.services.partner_accounting_service import PartnerAccountingService
            try:
                voucher_service_obj = Service.objects.filter(
                    Q(code='VOUCHER') | Q(code='GIFT_VOUCHER') | Q(name__icontains='voucher')
                ).filter(status='active').first()
                if voucher_service_obj:
                    accounting_service = PartnerAccountingService()
                    accounting_service.record_transaction(
                        partner=partner,
                        service=voucher_service_obj,
                        transaction_type='REVENUE',
                        amount=Decimal(amount_redeemed or '0'),
                        api_key=api_key,
                        reference_id=result.get('reference_number'),
                        description=f'Voucher redeemed: {format_voucher_code(voucher_code)}',
                        metadata={'voucher_id': voucher.id if voucher else None, 'redemption_method': 'PIN'}
                    )
            except Exception as e:
                logger.error(f'Error recording transaction: {str(e)}', exc_info=True)
            
            log_voucher_operation(
                operation='voucher_redeemed_pin_api_v2',
                log_level='INFO',
                message=f'Voucher redeemed via API v2 (PIN) - Code: {voucher_code[:8]}...',
                user_id=None,
                extra_data={
                    'voucher_id': voucher.id if voucher else None,
                    'voucher_code': format_voucher_code(voucher_code),
                    'amount': str(amount_redeemed),
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            return self.success_response(
                message="Voucher redeemed successfully",
                data={
                    'voucher_code': format_voucher_code(voucher_code),
                    'amount_redeemed': str(amount_redeemed),
                    'remaining_balance': str(remaining),
                    'transaction_id': result.get('transaction_id'),
                    'reference_number': result.get('reference_number')
                },
                request=request
            )
            
        except ValueError as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        except Exception as e:
            logger.error(f'Error redeeming voucher via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to redeem voucher",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class VoucherRedeemOTPRequestView(StandardResponseMixin, views.APIView):
    """
    Request OTP for voucher redemption
    POST /api/v2/vouchers/redeem-otp/request/
    
    Requires permission: voucher.redeem
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'voucher'
    required_action = 'redeem'
    
    def post(self, request):
        """Request OTP for redemption"""
        serializer = VoucherRedeemOTPRequestSerializer(data=request.data)
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
            
            voucher_code = unformat_voucher_code(serializer.validated_data['voucher_code'])
            mobile_number = serializer.validated_data['mobile_number']
            
            # Get voucher
            try:
                voucher = GiftVoucher.objects.get(voucher_code=voucher_code)
            except GiftVoucher.DoesNotExist:
                return self.error_response(
                    message="Voucher not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    request=request
                )
            
            # Request OTP
            voucher_service = VoucherService()
            result = voucher_service.request_redemption_otp(
                voucher_code=voucher_code,
                mobile_number=mobile_number,
                metadata={
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            if not result.get('success'):
                return self.error_response(
                    message=result.get('error', 'OTP request failed'),
                    status_code=status.HTTP_400_BAD_REQUEST,
                    request=request
                )
            
            return self.success_response(
                message="OTP sent successfully",
                data={
                    'voucher_code': format_voucher_code(voucher_code),
                    'otp_sent': True,
                    'mobile_number': mobile_number[-4:].rjust(len(mobile_number), '*')  # Masked
                },
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error requesting OTP via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to request OTP",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class VoucherRedeemOTPVerifyView(IdempotencyMixin, StandardResponseMixin, views.APIView):
    """
    Verify OTP and redeem voucher
    POST /api/v2/vouchers/redeem-otp/verify/
    Idempotent: X-Idempotency-Key or idempotency_key in body (24h TTL).
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    idempotency_scope_suffix = "v2:voucher_redeem_otp"
    service_name = 'voucher'
    required_action = 'redeem'
    
    def post(self, request):
        """Verify OTP and redeem"""
        serializer = VoucherRedeemOTPVerifySerializer(data=request.data)
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
            
            voucher_code = unformat_voucher_code(serializer.validated_data['voucher_code'])
            otp = serializer.validated_data['otp']
            redemption_amount = serializer.validated_data.get('amount')
            
            try:
                voucher = GiftVoucher.objects.get(voucher_code=voucher_code)
            except GiftVoucher.DoesNotExist:
                return self.error_response(
                    message="Voucher not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    request=request
                )
            amount_to_redeem = redemption_amount if redemption_amount is not None else voucher.current_balance
            
            voucher_service = VoucherService()
            result = voucher_service.redeem_voucher_otp(
                voucher_code=voucher_code,
                otp=otp,
                amount=amount_to_redeem,
                transaction_ref=serializer.validated_data.get('transaction_ref'),
                ip_address=self.get_client_ip(request),
            )
            amount_redeemed = result.get('redeemed_amount', '')
            remaining = result.get('balance_after', '')
            
            log_voucher_operation(
                operation='voucher_redeemed_otp_api_v2',
                log_level='INFO',
                message=f'Voucher redeemed via API v2 (OTP) - Code: {voucher_code[:8]}...',
                user_id=None,
                extra_data={
                    'voucher_id': voucher.id,
                    'voucher_code': format_voucher_code(voucher_code),
                    'amount': str(amount_redeemed),
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            return self.success_response(
                message="Voucher redeemed successfully",
                data={
                    'voucher_code': format_voucher_code(voucher_code),
                    'amount_redeemed': str(amount_redeemed),
                    'remaining_balance': str(remaining),
                    'transaction_id': result.get('transaction_id'),
                    'reference_number': result.get('reference_number')
                },
                request=request
            )
            
        except ValueError as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        except Exception as e:
            logger.error(f'Error redeeming voucher with OTP via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to redeem voucher",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


class VoucherBalanceView(StandardResponseMixin, views.APIView):
    """
    Check voucher balance
    GET /api/v2/vouchers/{voucher_code}/balance/
    
    Requires permission: voucher.balance
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'voucher'
    required_action = 'balance'
    
    def get(self, request, voucher_code):
        """Get voucher balance"""
        try:
            partner = request.partner
            api_key = request.api_key
            
            # Unformat voucher code
            voucher_code = unformat_voucher_code(voucher_code)
            
            # Get voucher
            try:
                voucher = GiftVoucher.objects.select_related('brand', 'client').get(voucher_code=voucher_code)
            except GiftVoucher.DoesNotExist:
                return self.error_response(
                    message="Voucher not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    request=request
                )
            
            serializer = VoucherBalanceResponseSerializer({
                'voucher_code': format_voucher_code(voucher.voucher_code),
                'reference_number': voucher.reference_number,
                'original_amount': voucher.original_amount,
                'current_balance': voucher.current_balance,
                'currency': voucher.currency,
                'status': voucher.status,
                'brand_name': voucher.brand.brand_name if voucher.brand else None,
                'issued_at': voucher.issued_at
            })
            
            return self.success_response(
                message="Voucher balance retrieved successfully",
                data=serializer.data,
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error getting voucher balance via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to get voucher balance",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class VoucherPINChangeRequestView(StandardResponseMixin, views.APIView):
    """
    Request OTP for PIN change
    POST /api/v2/vouchers/{voucher_code}/pin/change/request/
    
    Requires permission: voucher.pin_change
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'voucher'
    required_action = 'pin_change'
    
    def post(self, request, voucher_code):
        """Request OTP for PIN change"""
        serializer = VoucherPINChangeRequestSerializer(data=request.data)
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
            
            voucher_code = unformat_voucher_code(voucher_code)
            mobile_number = serializer.validated_data['mobile_number']
            
            # Get voucher
            try:
                voucher = GiftVoucher.objects.get(voucher_code=voucher_code)
            except GiftVoucher.DoesNotExist:
                return self.error_response(
                    message="Voucher not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    request=request
                )
            
            # Request OTP
            voucher_service = VoucherService()
            result = voucher_service.request_pin_change_otp(
                voucher_code=voucher_code,
                mobile_number=mobile_number,
                metadata={
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            if not result.get('success'):
                return self.error_response(
                    message=result.get('error', 'OTP request failed'),
                    status_code=status.HTTP_400_BAD_REQUEST,
                    request=request
                )
            
            return self.success_response(
                message="OTP sent successfully",
                data={
                    'voucher_code': format_voucher_code(voucher_code),
                    'otp_sent': True
                },
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error requesting PIN change OTP via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to request OTP",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class VoucherPINChangeVerifyView(StandardResponseMixin, views.APIView):
    """
    Verify OTP and change PIN
    POST /api/v2/vouchers/{voucher_code}/pin/change/verify/
    
    Requires permission: voucher.pin_change
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission]
    parser_classes = [JSONParser]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'voucher'
    required_action = 'pin_change'
    
    def post(self, request, voucher_code):
        """Verify OTP and change PIN"""
        serializer = VoucherPINChangeVerifySerializer(data=request.data)
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
            
            voucher_code = unformat_voucher_code(voucher_code)
            otp = serializer.validated_data['otp']
            new_pin = serializer.validated_data['new_pin']
            
            # Get voucher
            try:
                voucher = GiftVoucher.objects.get(voucher_code=voucher_code)
            except GiftVoucher.DoesNotExist:
                return self.error_response(
                    message="Voucher not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    request=request
                )
            
            # Change PIN
            voucher_service = VoucherService()
            result = voucher_service.change_pin_with_otp(
                voucher_code=voucher_code,
                otp=otp,
                new_pin=new_pin,
                metadata={
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            if not result.get('success'):
                return self.error_response(
                    message=result.get('error', 'PIN change failed'),
                    status_code=status.HTTP_400_BAD_REQUEST,
                    request=request
                )
            
            # Log operation
            log_voucher_operation(
                operation='voucher_pin_changed_api_v2',
                log_level='INFO',
                message=f'Voucher PIN changed via API v2 - Code: {voucher_code[:8]}...',
                user_id=None,
                extra_data={
                    'voucher_id': voucher.id,
                    'voucher_code': format_voucher_code(voucher_code),
                    'partner_id': partner.id,
                    'partner_code': partner.partner_code,
                    'api_key_id': api_key.id
                }
            )
            
            return self.success_response(
                message="PIN changed successfully",
                data={
                    'voucher_code': format_voucher_code(voucher_code),
                    'pin_changed': True
                },
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error changing PIN via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to change PIN",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class VoucherBatchListView(StandardResponseMixin, views.APIView):
    """
    List voucher batches
    GET /api/v2/vouchers/batches/
    
    Requires permission: voucher.batch_view
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'voucher'
    required_action = 'batch_view'
    
    def get(self, request):
        """List batches for this partner"""
        try:
            partner = request.partner
            
            # Get batches (filter by partner metadata if needed)
            batches = BulkVoucherIssuanceBatch.objects.filter(
                metadata__partner_id=partner.id
            ).select_related('brand', 'client').order_by('-created_at')[:50]
            
            serializer = VoucherBatchListSerializer(batches, many=True)
            
            return self.success_response(
                message="Batches retrieved successfully",
                data=serializer.data,
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error listing batches via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to retrieve batches",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class VoucherBatchDetailView(StandardResponseMixin, views.APIView):
    """
    Get batch details
    GET /api/v2/vouchers/batches/{batch_id}/
    
    Requires permission: voucher.batch_view
    """
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [HasAPIKey, HasServicePermission]
    throttle_classes = [APIKeyRateThrottle, ServiceRateThrottle]
    
    service_name = 'voucher'
    required_action = 'batch_view'
    
    def get(self, request, batch_id):
        """Get batch details"""
        try:
            partner = request.partner
            
            # Get batch
            try:
                batch = BulkVoucherIssuanceBatch.objects.select_related('brand', 'client').get(
                    id=batch_id,
                    metadata__partner_id=partner.id
                )
            except BulkVoucherIssuanceBatch.DoesNotExist:
                return self.error_response(
                    message="Batch not found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    request=request
                )
            
            serializer = VoucherBatchDetailSerializer(batch)
            
            return self.success_response(
                message="Batch details retrieved successfully",
                data=serializer.data,
                request=request
            )
            
        except Exception as e:
            logger.error(f'Error getting batch details via API v2: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to get batch details",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )
