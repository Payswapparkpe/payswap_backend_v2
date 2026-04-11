"""
Voucher Management Views for API v1
"""
from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count, F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from api.mixins.response_mixin import StandardResponseMixin
from api.mixins.logging_mixin import APILoggingMixin
from portal.models import (
    GiftVoucherBrand, GiftVoucher, GiftVoucherTransaction,
    BulkVoucherIssuanceBatch, User, VoucherClient
)
from portal.services.voucher_service import VoucherService
from portal.services.bulk_voucher_service import BulkVoucherService
from portal.utils.voucher_errors import create_error_response, get_error_message
from portal.utils.logging_helper import get_logger
from portal.utils.voucher_logging import log_voucher_operation
from .voucher_serializers import (
    BrandSerializer, BrandCreateSerializer, BrandUpdateSerializer, BrandListSerializer,
    VoucherIssueSerializer, VoucherIssueResponseSerializer,
    VoucherRedeemPINSerializer, VoucherRedeemOTPRequestSerializer, VoucherRedeemOTPVerifySerializer,
    VoucherPINChangeRequestSerializer, VoucherPINChangeVerifySerializer,
    VoucherBalanceSerializer, VoucherBalanceResponseSerializer,
    BulkIssuanceUploadSerializer, BulkIssuanceStatusSerializer,
    IssuanceReportSerializer, RedemptionReportSerializer, OutstandingBalanceReportSerializer,
    VoucherClientSerializer, VoucherClientCreateSerializer, VoucherClientListSerializer
)

logger = get_logger('api.v1.voucher_views')


# ============================================================================
# BRAND MANAGEMENT VIEWS
# ============================================================================

class BrandViewSet(APILoggingMixin, StandardResponseMixin, viewsets.ModelViewSet):
    """
    Brand management ViewSet
    
    Endpoints:
    - POST /api/v1/vouchers/brands/ - Create brand
    - GET /api/v1/vouchers/brands/ - List brands (paginated)
    - GET /api/v1/vouchers/brands/{id}/ - Get brand details
    - PUT /api/v1/vouchers/brands/{id}/ - Update brand
    - PATCH /api/v1/vouchers/brands/{id}/ - Partial update brand
    - PATCH /api/v1/vouchers/brands/{id}/status/ - Update brand status
    """
    queryset = GiftVoucherBrand.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return BrandListSerializer
        elif self.action == 'create':
            return BrandCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return BrandUpdateSerializer
        return BrandSerializer
    
    def get_queryset(self):
        """Filter queryset based on permissions"""
        queryset = super().get_queryset()
        # Add any permission-based filtering here if needed
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        """Set created_by on brand creation"""
        serializer.save(created_by=self.request.user)
        
        # Log operation
        log_voucher_operation(
            operation='brand_created_api',
            log_level='INFO',
            message=f'Brand created via API: {serializer.instance.brand_name}',
            user_id=self.request.user.id,
            request=self.request,
            extra_data={
                'brand_id': serializer.instance.id,
                'brand_name': serializer.instance.brand_name,
                'brand_code': serializer.instance.brand_code
            }
        )
    
    def perform_update(self, serializer):
        """Set updated_by on brand update"""
        serializer.save(updated_by=self.request.user)
        
        # Log operation
        log_voucher_operation(
            operation='brand_updated_api',
            log_level='INFO',
            message=f'Brand updated via API: {serializer.instance.brand_name}',
            user_id=self.request.user.id,
            request=self.request,
            extra_data={
                'brand_id': serializer.instance.id,
                'brand_name': serializer.instance.brand_name
            }
        )
    
    @action(detail=True, methods=['patch'])
    def status(self, request, pk=None):
        """Update brand status"""
        brand = self.get_object()
        new_status = request.data.get('status')
        
        if new_status not in ['ACTIVE', 'INACTIVE', 'SUSPENDED']:
            return self.error_response(
                message="Invalid status. Must be one of: ACTIVE, INACTIVE, SUSPENDED",
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        
        old_status = brand.status
        brand.status = new_status
        brand.updated_by = request.user
        brand.save()
        
        # Log operation
        log_voucher_operation(
            operation='brand_status_updated_api',
            log_level='INFO',
            message=f'Brand status updated via API: {brand.brand_name} - {old_status} -> {new_status}',
            user_id=request.user.id,
            request=request,
            extra_data={
                'brand_id': brand.id,
                'brand_name': brand.brand_name,
                'old_status': old_status,
                'new_status': new_status
            }
        )
        
        serializer = self.get_serializer(brand)
        return self.success_response(
            message="Brand status updated successfully",
            data=serializer.data,
            request=request
        )
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# ============================================================================
# VOUCHER ISSUANCE VIEWS
# ============================================================================

class VoucherIssueView(APILoggingMixin, StandardResponseMixin, views.APIView):
    """Single voucher issuance view"""
    permission_classes = [IsAuthenticated]
    
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
            # Determine issuer type based on user role
            issuer_type = 'API_PARTNER'  # Default for API users
            if request.user.role_code == 'admin':
                issuer_type = 'ADMIN'
            elif request.user.role_code == 'brand_owner':
                issuer_type = 'BRAND_OWNER'
            
            voucher_service = VoucherService()
            result = voucher_service.issue_single_voucher(
                brand_id=serializer.validated_data['brand_id'],
                amount=serializer.validated_data['amount'],
                mobile_number=serializer.validated_data.get('mobile_number'),
                metadata=serializer.validated_data.get('metadata'),
                created_by=request.user,
                client_id=serializer.validated_data.get('client_id'),
                issued_by=request.user,
                issuer_type=issuer_type
            )
            
            # Log operation
            log_voucher_operation(
                operation='voucher_issued_api',
                log_level='INFO',
                message=f'Voucher issued via API - Reference: {result["reference_number"]}',
                user_id=request.user.id,
                request=request,
                extra_data={
                    'voucher_id': result['voucher_id'],
                    'reference_number': result['reference_number'],
                    'brand_id': serializer.validated_data['brand_id'],
                    'amount': str(result['amount']),
                    'issuer_type': issuer_type
                }
            )
            
            response_serializer = VoucherIssueResponseSerializer(result)
            return self.success_response(
                message="Voucher issued successfully",
                data=response_serializer.data,
                request=request
            )
            
        except ValueError as e:
            log_voucher_operation(
                operation='voucher_issuance_failed_api',
                log_level='WARNING',
                message=f'Voucher issuance failed via API (validation): {str(e)}',
                user_id=request.user.id,
                request=request,
                extra_data={'error': str(e), 'brand_id': serializer.validated_data.get('brand_id')}
            )
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        except Exception as e:
            log_voucher_operation(
                operation='voucher_issuance_failed_api',
                log_level='ERROR',
                message=f'Voucher issuance failed via API: {str(e)}',
                user_id=request.user.id,
                request=request,
                extra_data={'error': str(e)},
                exception=e
            )
            logger.error(f'Error issuing voucher: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to issue voucher",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class BulkVoucherIssueView(APILoggingMixin, StandardResponseMixin, views.APIView):
    """Bulk voucher issuance view"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        """Upload bulk voucher file"""
        serializer = BulkIssuanceUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        
        try:
            from portal.utils.voucher_utils import generate_reference_number
            from portal.tasks.voucher_tasks import process_bulk_voucher_issuance_task
            
            bulk_service = BulkVoucherService()
            file = serializer.validated_data['file']
            brand_id = serializer.validated_data['brand_id']
            
            # Validate file
            is_valid, error_msg = bulk_service.validate_upload_file(file)
            if not is_valid:
                return self.error_response(
                    message=error_msg,
                    status_code=status.HTTP_400_BAD_REQUEST,
                    request=request
                )
            
            # Parse file
            voucher_data, parse_error = bulk_service.parse_upload_file(file)
            if not voucher_data:
                return self.error_response(
                    message=parse_error or "Failed to parse file",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    request=request
                )
            
            # Determine issuer type
            issuer_type = 'API_PARTNER'
            if request.user.role_code == 'admin':
                issuer_type = 'ADMIN'
            elif request.user.role_code == 'brand_owner':
                issuer_type = 'BRAND_OWNER'
            
            client_id = serializer.validated_data.get('client_id')
            issuance_method = serializer.validated_data.get('issuance_method', 'FILE_UPLOAD')
            denominations = serializer.validated_data.get('denominations', [])
            
            # Handle manual bulk issuance
            if issuance_method == 'MANUAL_BULK' and denominations:
                batch = bulk_service.create_manual_bulk_batch(
                    brand_id=brand_id,
                    client_id=client_id,
                    denominations=denominations,
                    issued_by=request.user,
                    issuer_type=issuer_type
                )
                process_bulk_voucher_issuance_task.delay(batch.id)
            else:
                # File upload (existing logic)
                # Get or create default client if not provided
                if not client_id:
                    from portal.services.voucher_client_service import VoucherClientService
                    client_service = VoucherClientService()
                    client = client_service.get_or_create_default_client(brand_id)
                    client_id = client.id
                
                # Create batch record first
                batch = BulkVoucherIssuanceBatch.objects.create(
                    brand_id=brand_id,
                    client_id=client_id,
                    batch_reference=generate_reference_number('BATCH'),
                    batch_reference_number=generate_reference_number('BRN'),
                    total_vouchers=len(voucher_data),
                    status='PENDING',
                    issuance_method='FILE_UPLOAD',
                    issued_by=request.user,
                    issuer_type=issuer_type,
                    created_by=request.user
                )
            
                # Upload file to S3 with batch_id
                try:
                    uploaded_file_path = bulk_service.upload_file_to_s3(file, batch.id)
                    batch.uploaded_file_path = uploaded_file_path
                    batch.save()
                except Exception as e:
                    logger.error(f'Failed to upload file to S3: {str(e)}')
                    # Continue without S3 upload
                
                # Queue Celery task for processing
                process_bulk_voucher_issuance_task.delay(batch.id)
            
            # Log operation
            log_voucher_operation(
                operation='bulk_issuance_queued_api',
                log_level='INFO',
                message=f'Bulk voucher issuance queued - Batch: {batch.batch_reference}',
                user_id=request.user.id,
                request=request,
                extra_data={
                    'batch_id': batch.id,
                    'batch_reference': batch.batch_reference,
                    'total_vouchers': batch.total_vouchers
                }
            )
            
            response_serializer = BulkIssuanceStatusSerializer(batch)
            return self.success_response(data=response_serializer.data)
            
        except Exception as e:
            logger.error(f'Error processing bulk upload: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to process bulk upload",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


# ============================================================================
# CLIENT MANAGEMENT VIEWS
# ============================================================================

class VoucherClientViewSet(APILoggingMixin, StandardResponseMixin, viewsets.ModelViewSet):
    """
    Voucher Client management ViewSet
    
    Endpoints:
    - POST /api/v1/vouchers/clients/ - Create client
    - GET /api/v1/vouchers/clients/ - List clients (with brand filter)
    - GET /api/v1/vouchers/clients/{id}/ - Get client details
    - PUT /api/v1/vouchers/clients/{id}/ - Update client
    - PATCH /api/v1/vouchers/clients/{id}/ - Partial update client
    - DELETE /api/v1/vouchers/clients/{id}/ - Deactivate client
    """
    queryset = VoucherClient.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['brand', 'status', 'is_default']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return VoucherClientListSerializer
        elif self.action == 'create':
            return VoucherClientCreateSerializer
        return VoucherClientSerializer
    
    def get_queryset(self):
        """Filter queryset"""
        queryset = super().get_queryset().select_related('brand', 'created_by')
        brand_id = self.request.query_params.get('brand_id')
        if brand_id:
            queryset = queryset.filter(brand_id=brand_id)
        return queryset.order_by('-is_default', '-created_at')
    
    def perform_create(self, serializer):
        """Set created_by on client creation"""
        from portal.services.voucher_client_service import VoucherClientService
        
        client_service = VoucherClientService()
        client = client_service.create_client(
            brand_id=serializer.validated_data['brand'].id,
            client_data={
                'client_name': serializer.validated_data['client_name'],
                'contact_person': serializer.validated_data.get('contact_person'),
                'contact_email': serializer.validated_data.get('contact_email'),
                'contact_phone': serializer.validated_data.get('contact_phone'),
                'is_default': serializer.validated_data.get('is_default', False),
                'status': serializer.validated_data.get('status', 'ACTIVE')
            },
            created_by=self.request.user
        )
        serializer.instance = client
    
    def perform_update(self, serializer):
        """Update client"""
        from portal.services.voucher_client_service import VoucherClientService
        
        client_service = VoucherClientService()
        client = client_service.update_client(
            client_id=serializer.instance.id,
            client_data={
                'client_name': serializer.validated_data.get('client_name'),
                'contact_person': serializer.validated_data.get('contact_person'),
                'contact_email': serializer.validated_data.get('contact_email'),
                'contact_phone': serializer.validated_data.get('contact_phone'),
                'status': serializer.validated_data.get('status'),
                'is_default': serializer.validated_data.get('is_default', False)
            }
        )
        serializer.instance = client
    
    def destroy(self, request, *args, **kwargs):
        """Deactivate client instead of deleting"""
        from portal.services.voucher_client_service import VoucherClientService
        
        client_service = VoucherClientService()
        try:
            client_service.deactivate_client(self.get_object().id)
            return self.success_response(
                message="Client deactivated successfully",
                request=request
            )
        except ValueError as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )


# ============================================================================
# EXPORT VIEWS
# ============================================================================

class BatchExportView(APILoggingMixin, StandardResponseMixin, views.APIView):
    """Export batch to CSV/Excel"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, batch_id):
        """Export batch"""
        from portal.services.voucher_export_service import VoucherExportService
        
        format_type = request.query_params.get('format', 'csv')
        export_service = VoucherExportService()
        
        try:
            if format_type == 'excel':
                return export_service.export_batch_to_excel(batch_id)
            else:
                return export_service.export_batch_to_csv(batch_id)
        except ValueError as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        except Exception as e:
            logger.error(f'Error exporting batch: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to export batch",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class BatchStatusView(APILoggingMixin, StandardResponseMixin, views.APIView):
    """Get bulk issuance batch status"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, batch_id):
        """Get bulk issuance status"""
        try:
            batch = BulkVoucherIssuanceBatch.objects.get(id=batch_id)
            response_serializer = BulkIssuanceStatusSerializer(batch)
            return self.success_response(
                message="Batch status retrieved successfully",
                data=response_serializer.data,
                request=request
            )
        except BulkVoucherIssuanceBatch.DoesNotExist:
            return self.error_response(
                message="Batch not found",
                status_code=status.HTTP_404_NOT_FOUND,
                request=request
            )
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# ============================================================================
# VOUCHER REDEMPTION VIEWS
# ============================================================================

class VoucherRedeemPINView(APILoggingMixin, StandardResponseMixin, views.APIView):
    """PIN-based redemption view"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Redeem voucher using PIN"""
        serializer = VoucherRedeemPINSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        
        try:
            voucher_service = VoucherService()
            result = voucher_service.redeem_voucher_pin(
                voucher_code=serializer.validated_data['voucher_code'],
                pin=serializer.validated_data['pin'],
                amount=serializer.validated_data['amount'],
                transaction_ref=serializer.validated_data.get('transaction_ref'),
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            # Log operation
            log_voucher_operation(
                operation='voucher_redeemed_pin_api',
                log_level='INFO',
                message=f'Voucher redeemed via PIN - Reference: {result["reference_number"]}',
                user_id=request.user.id,
                request=request,
                extra_data={
                    'transaction_id': result['transaction_id'],
                    'voucher_code': serializer.validated_data['voucher_code'],
                    'amount': str(result['redeemed_amount'])
                }
            )
            
            return self.success_response(
                message="Voucher redeemed successfully",
                data=result,
                request=request
            )
            
        except ValueError as e:
            error_msg = str(e)
            # Check if it's a PIN-related error
            if 'PIN' in error_msg or 'pin' in error_msg.lower():
                return self.error_response(
                    message=error_msg,
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    request=request
                )
            return self.error_response(
                message=error_msg,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        except Exception as e:
            logger.error(f'Error redeeming voucher: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to redeem voucher",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class VoucherRedeemOTPRequestView(APILoggingMixin, StandardResponseMixin, views.APIView):
    """OTP request view for redemption"""
    permission_classes = [IsAuthenticated]
    
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
            voucher_service = VoucherService()
            result = voucher_service.generate_otp_for_voucher(
                voucher_code=serializer.validated_data['voucher_code'],
                otp_purpose='REDEMPTION',
                ip_address=self.get_client_ip(request)
            )
            
            return self.success_response(
                message="OTP sent successfully",
                data=result,
                request=request
            )
            
        except ValueError as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        except Exception as e:
            logger.error(f'Error requesting OTP: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to send OTP",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class VoucherRedeemOTPVerifyView(APILoggingMixin, StandardResponseMixin, views.APIView):
    """OTP verification and redemption view"""
    permission_classes = [IsAuthenticated]
    
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
            voucher_service = VoucherService()
            result = voucher_service.redeem_voucher_otp(
                voucher_code=serializer.validated_data['voucher_code'],
                otp=serializer.validated_data['otp'],
                amount=serializer.validated_data['amount'],
                transaction_ref=serializer.validated_data.get('transaction_ref'),
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            # Log operation
            log_voucher_operation(
                operation='voucher_redeemed_otp_api',
                log_level='INFO',
                message=f'Voucher redeemed via OTP - Reference: {result["reference_number"]}',
                user_id=request.user.id,
                request=request,
                extra_data={
                    'transaction_id': result['transaction_id'],
                    'voucher_code': serializer.validated_data['voucher_code'],
                    'amount': str(result['redeemed_amount'])
                }
            )
            
            return self.success_response(
                message="Voucher redeemed successfully",
                data=result,
                request=request
            )
            
        except ValueError as e:
            error_msg = str(e)
            if 'OTP' in error_msg or 'otp' in error_msg.lower():
                return self.error_response(
                    message=error_msg,
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    request=request
                )
            return self.error_response(
                message=error_msg,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        except Exception as e:
            logger.error(f'Error redeeming voucher with OTP: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to redeem voucher",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# ============================================================================
# PIN MANAGEMENT VIEWS
# ============================================================================

class VoucherPINChangeRequestView(APILoggingMixin, StandardResponseMixin, views.APIView):
    """PIN change OTP request view"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
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
            voucher_service = VoucherService()
            result = voucher_service.generate_otp_for_voucher(
                voucher_code=serializer.validated_data['voucher_code'],
                otp_purpose='PIN_CHANGE',
                ip_address=self.get_client_ip(request)
            )
            
            return self.success_response(
                message="OTP sent successfully",
                data=result,
                request=request
            )
            
        except ValueError as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        except Exception as e:
            logger.error(f'Error requesting PIN change OTP: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to send OTP",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


class VoucherPINChangeVerifyView(APILoggingMixin, StandardResponseMixin, views.APIView):
    """PIN change verification view"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
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
            voucher_service = VoucherService()
            result = voucher_service.change_pin(
                voucher_code=serializer.validated_data['voucher_code'],
                otp=serializer.validated_data['otp'],
                new_pin=serializer.validated_data['new_pin'],
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            # Log operation
            log_voucher_operation(
                operation='pin_changed_api',
                log_level='INFO',
                message=f'PIN changed for voucher: {serializer.validated_data["voucher_code"]}',
                user_id=request.user.id,
                request=request,
                extra_data={'voucher_code': serializer.validated_data['voucher_code']}
            )
            
            return self.success_response(
                message="PIN changed successfully",
                data=result,
                request=request
            )
            
        except ValueError as e:
            error_msg = str(e)
            if 'OTP' in error_msg or 'otp' in error_msg.lower():
                return self.error_response(
                    message=error_msg,
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    request=request
                )
            return self.error_response(
                message=error_msg,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        except Exception as e:
            logger.error(f'Error changing PIN: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to change PIN",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


# ============================================================================
# BALANCE INQUIRY VIEW
# ============================================================================

class VoucherBalanceView(APILoggingMixin, StandardResponseMixin, views.APIView):
    """Balance inquiry view"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Check voucher balance"""
        serializer = VoucherBalanceSerializer(data=request.data)
        if not serializer.is_valid():
            return self.error_response(
                message="Invalid request data",
                errors=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        
        try:
            voucher_service = VoucherService()
            result = voucher_service.check_balance(
                voucher_code=serializer.validated_data['voucher_code'],
                pin=serializer.validated_data['pin'],
                include_transactions=serializer.validated_data.get('include_transactions', False)
            )
            
            response_serializer = VoucherBalanceResponseSerializer(result)
            return self.success_response(data=response_serializer.data)
            
        except ValueError as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
                request=request
            )
        except Exception as e:
            logger.error(f'Error checking balance: {str(e)}', exc_info=True)
            return self.error_response(
                message="Failed to check balance",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                request=request
            )


# ============================================================================
# REPORTING VIEWS
# ============================================================================

class VoucherIssuanceReportView(APILoggingMixin, StandardResponseMixin, views.APIView):
    """Issuance report view"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get issuance report"""
        from django.core.paginator import Paginator
        
        brand_id = request.query_params.get('brand_id')
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        voucher_status = request.query_params.get('status')
        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 50))
        
        # Build query
        queryset = GiftVoucher.objects.select_related('brand', 'created_by').all()
        
        if brand_id:
            queryset = queryset.filter(brand_id=brand_id)
        if voucher_status:
            queryset = queryset.filter(status=voucher_status)
        if from_date:
            queryset = queryset.filter(issued_at__gte=from_date)
        if to_date:
            queryset = queryset.filter(issued_at__lte=to_date)
        
        # Paginate
        paginator = Paginator(queryset, limit)
        page_obj = paginator.get_page(page)
        
        # Calculate totals
        total_count = queryset.count()
        total_amount = queryset.aggregate(total=Sum('original_amount'))['total'] or Decimal('0.00')
        
        # Serialize items
        items = []
        for voucher in page_obj:
            items.append({
                'voucher_id': voucher.id,
                'reference_number': voucher.reference_number,
                'voucher_code': voucher.voucher_code,  # Format in serializer if needed
                'brand_name': voucher.brand.brand_name,
                'amount': str(voucher.original_amount),
                'status': voucher.status,
                'issued_at': voucher.issued_at,
                'created_by': voucher.created_by.username if voucher.created_by else None
            })
        
        result = {
            'total_count': total_count,
            'total_amount': str(total_amount),
            'items': items,
            'page': page,
            'page_size': limit,
            'total_pages': paginator.num_pages
        }
        
        serializer = IssuanceReportSerializer(result)
        return self.success_response(
            message="Issuance report retrieved successfully",
            data=serializer.data,
            request=request
        )


class VoucherRedemptionReportView(APILoggingMixin, StandardResponseMixin, views.APIView):
    """Redemption report view"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get redemption report"""
        from django.core.paginator import Paginator
        
        brand_id = request.query_params.get('brand_id')
        from_date = request.query_params.get('from_date')
        to_date = request.query_params.get('to_date')
        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 50))
        
        # Build query
        queryset = GiftVoucherTransaction.objects.filter(
            transaction_type='REDEMPTION',
            transaction_status='SUCCESS'
        ).select_related('voucher', 'voucher__brand')
        
        if brand_id:
            queryset = queryset.filter(voucher__brand_id=brand_id)
        if from_date:
            queryset = queryset.filter(created_at__gte=from_date)
        if to_date:
            queryset = queryset.filter(created_at__lte=to_date)
        
        # Paginate
        paginator = Paginator(queryset, limit)
        page_obj = paginator.get_page(page)
        
        # Calculate totals
        total_count = queryset.count()
        total_amount = queryset.aggregate(total=Sum('transaction_amount'))['total'] or Decimal('0.00')
        
        # Serialize items
        items = []
        for txn in page_obj:
            items.append({
                'transaction_id': txn.id,
                'voucher_code': txn.voucher.voucher_code,
                'reference_number': txn.voucher.reference_number,
                'brand_name': txn.voucher.brand.brand_name,
                'redeemed_amount': str(txn.transaction_amount),
                'redemption_method': txn.redemption_method,
                'transaction_status': txn.transaction_status,
                'created_at': txn.created_at
            })
        
        result = {
            'total_count': total_count,
            'total_amount': str(total_amount),
            'items': items,
            'page': page,
            'page_size': limit,
            'total_pages': paginator.num_pages
        }
        
        serializer = RedemptionReportSerializer(result)
        return self.success_response(
            message="Redemption report retrieved successfully",
            data=serializer.data,
            request=request
        )


class VoucherOutstandingBalanceReportView(APILoggingMixin, StandardResponseMixin, views.APIView):
    """Outstanding balance report view"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get outstanding balance report"""
        from django.core.paginator import Paginator
        
        brand_id = request.query_params.get('brand_id')
        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 50))
        
        # Build query - vouchers that are not fully redeemed
        queryset = GiftVoucher.objects.filter(
            status__in=['ACTIVE', 'PARTIALLY_REDEEMED']
        ).select_related('brand')
        
        if brand_id:
            queryset = queryset.filter(brand_id=brand_id)
        
        # Paginate
        paginator = Paginator(queryset, limit)
        page_obj = paginator.get_page(page)
        
        # Calculate totals
        total_count = queryset.count()
        total_outstanding = queryset.aggregate(total=Sum('current_balance'))['total'] or Decimal('0.00')
        total_issued = queryset.aggregate(total=Sum('original_amount'))['total'] or Decimal('0.00')
        total_redeemed = total_issued - total_outstanding
        
        # Serialize items
        items = []
        for voucher in page_obj:
            redeemed_amount = voucher.original_amount - voucher.current_balance
            items.append({
                'voucher_id': voucher.id,
                'voucher_code': voucher.voucher_code,
                'reference_number': voucher.reference_number,
                'brand_name': voucher.brand.brand_name,
                'original_amount': str(voucher.original_amount),
                'current_balance': str(voucher.current_balance),
                'redeemed_amount': str(redeemed_amount),
                'status': voucher.status,
                'issued_at': voucher.issued_at,
                'last_transaction_at': voucher.last_transaction_at
            })
        
        result = {
            'total_count': total_count,
            'total_outstanding': str(total_outstanding),
            'total_issued': str(total_issued),
            'total_redeemed': str(total_redeemed),
            'items': items,
            'page': page,
            'page_size': limit,
            'total_pages': paginator.num_pages
        }
        
        serializer = OutstandingBalanceReportSerializer(result)
        return self.success_response(
            message="Outstanding balance report retrieved successfully",
            data=serializer.data,
            request=request
        )
