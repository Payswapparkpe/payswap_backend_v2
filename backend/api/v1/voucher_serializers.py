"""
Serializers for Gift Voucher APIs
"""
from rest_framework import serializers
from decimal import Decimal
from portal.models import (
    GiftVoucherBrand, GiftVoucher, GiftVoucherTransaction,
    BulkVoucherIssuanceBatch, VoucherClient
)


# ============================================================================
# BRAND SERIALIZERS
# ============================================================================

class BrandListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for brand list"""
    
    class Meta:
        model = GiftVoucherBrand
        fields = ['id', 'brand_code', 'brand_name', 'status', 'created_at']
        read_only_fields = ['id', 'brand_code', 'created_at']


class BrandSerializer(serializers.ModelSerializer):
    """Full brand details serializer"""
    
    class Meta:
        model = GiftVoucherBrand
        fields = [
            'id', 'brand_code', 'brand_name', 'business_reg_no',
            'contact_person', 'contact_email', 'contact_phone',
            'address', 'status', 'created_at', 'updated_at',
            'created_by', 'updated_by'
        ]
        read_only_fields = ['id', 'brand_code', 'created_at', 'updated_at']


class BrandCreateSerializer(serializers.ModelSerializer):
    """Serializer for brand creation"""
    
    class Meta:
        model = GiftVoucherBrand
        fields = [
            'brand_name', 'business_reg_no', 'contact_person',
            'contact_email', 'contact_phone', 'address', 'status'
        ]
    
    def validate(self, attrs):
        """Validate brand data"""
        # Brand code is auto-generated, so no need to validate it
        return attrs


class BrandUpdateSerializer(serializers.ModelSerializer):
    """Serializer for brand updates"""
    
    class Meta:
        model = GiftVoucherBrand
        fields = [
            'brand_name', 'business_reg_no', 'contact_person',
            'contact_email', 'contact_phone', 'address', 'status'
        ]


# ============================================================================
# VOUCHER ISSUANCE SERIALIZERS
# ============================================================================

class VoucherIssueSerializer(serializers.Serializer):
    """Serializer for single voucher issuance"""
    
    brand_id = serializers.IntegerField(required=True)
    client_id = serializers.IntegerField(required=False, allow_null=True)
    amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=True,
        min_value=Decimal('0.01')
    )
    mobile_number = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    metadata = serializers.JSONField(required=False, default=dict)


class VoucherIssueResponseSerializer(serializers.Serializer):
    """Response serializer for voucher issuance"""
    
    voucher_id = serializers.IntegerField()
    reference_number = serializers.CharField()
    voucher_code = serializers.CharField()
    pin = serializers.CharField()  # Only shown once during issuance
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    currency = serializers.CharField()
    status = serializers.CharField()
    issued_at = serializers.DateTimeField()
    mobile_number = serializers.CharField(allow_null=True)
    client_name = serializers.CharField(allow_null=True)
    client_code = serializers.CharField(allow_null=True)
    issued_by = serializers.CharField(allow_null=True)
    issuer_type = serializers.CharField(allow_null=True)


# ============================================================================
# VOUCHER REDEMPTION SERIALIZERS
# ============================================================================

class VoucherRedeemPINSerializer(serializers.Serializer):
    """Serializer for PIN-based redemption"""
    
    voucher_code = serializers.CharField(required=True, max_length=25)  # With or without hyphens
    pin = serializers.CharField(required=True, min_length=4, max_length=4)
    amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=True,
        min_value=Decimal('0.01')
    )
    transaction_ref = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True
    )


class VoucherRedeemOTPRequestSerializer(serializers.Serializer):
    """Serializer for OTP request"""
    
    voucher_code = serializers.CharField(required=True, max_length=25)


class VoucherRedeemOTPVerifySerializer(serializers.Serializer):
    """Serializer for OTP verification and redemption"""
    
    voucher_code = serializers.CharField(required=True, max_length=25)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)
    amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=True,
        min_value=Decimal('0.01')
    )
    transaction_ref = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        allow_null=True
    )


# ============================================================================
# PIN MANAGEMENT SERIALIZERS
# ============================================================================

class VoucherPINChangeRequestSerializer(serializers.Serializer):
    """Serializer for PIN change OTP request"""
    
    voucher_code = serializers.CharField(required=True, max_length=25)


class VoucherPINChangeVerifySerializer(serializers.Serializer):
    """Serializer for PIN change verification"""
    
    voucher_code = serializers.CharField(required=True, max_length=25)
    otp = serializers.CharField(required=True, min_length=6, max_length=6)
    new_pin = serializers.CharField(required=True, min_length=4, max_length=4)
    
    def validate_new_pin(self, value):
        """Validate new PIN format"""
        if not value.isdigit():
            raise serializers.ValidationError("PIN must contain only digits")
        if len(value) != 4:
            raise serializers.ValidationError("PIN must be exactly 4 digits")
        pin_int = int(value)
        if pin_int < 1000 or pin_int > 9999:
            raise serializers.ValidationError("PIN must be between 1000 and 9999")
        return value


# ============================================================================
# BALANCE INQUIRY SERIALIZERS
# ============================================================================

class VoucherBalanceSerializer(serializers.Serializer):
    """Serializer for balance inquiry"""
    
    voucher_code = serializers.CharField(required=True, max_length=25)
    pin = serializers.CharField(required=True, min_length=4, max_length=4)
    include_transactions = serializers.BooleanField(required=False, default=False)


class VoucherTransactionSerializer(serializers.ModelSerializer):
    """Serializer for transaction details"""
    
    class Meta:
        model = GiftVoucherTransaction
        fields = [
            'id', 'transaction_type', 'transaction_amount',
            'balance_before', 'balance_after', 'redemption_method',
            'transaction_status', 'created_at'
        ]
        read_only_fields = fields


class VoucherBalanceResponseSerializer(serializers.Serializer):
    """Response serializer for balance inquiry"""
    
    reference_number = serializers.CharField()
    current_balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    original_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    status = serializers.CharField()
    issued_at = serializers.DateTimeField()
    last_transaction_at = serializers.DateTimeField(allow_null=True)
    recent_transactions = VoucherTransactionSerializer(many=True, required=False)


# ============================================================================
# BULK ISSUANCE SERIALIZERS
# ============================================================================

class BulkIssuanceUploadSerializer(serializers.Serializer):
    """Serializer for bulk voucher file upload"""
    
    brand_id = serializers.IntegerField(required=True)
    client_id = serializers.IntegerField(required=False, allow_null=True)
    file = serializers.FileField(required=True)
    issuance_method = serializers.ChoiceField(
        choices=['FILE_UPLOAD', 'MANUAL_BULK'],
        default='FILE_UPLOAD',
        required=False
    )
    denominations = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()
        ),
        required=False,
        allow_empty=True
    )
    
    def validate_file(self, value):
        """Validate uploaded file"""
        file_name = value.name.lower()
        if not (file_name.endswith('.csv') or file_name.endswith('.xlsx') or file_name.endswith('.xls')):
            raise serializers.ValidationError("Only CSV and Excel files are supported")
        
        # Check file size (max 10MB)
        max_size = 10 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(f"File size exceeds maximum limit of {max_size / (1024*1024)}MB")
        
        return value


class BulkIssuanceStatusSerializer(serializers.ModelSerializer):
    """Serializer for bulk issuance batch status"""
    brand_name = serializers.CharField(source='brand.brand_name', read_only=True)
    client_name = serializers.CharField(source='client.client_name', read_only=True, allow_null=True)
    issued_by_username = serializers.CharField(source='issued_by.username', read_only=True, allow_null=True)
    issuer_type_display = serializers.CharField(source='get_issuer_type_display', read_only=True)
    issuance_method_display = serializers.CharField(source='get_issuance_method_display', read_only=True)
    
    class Meta:
        model = BulkVoucherIssuanceBatch
        fields = [
            'id', 'batch_reference', 'batch_reference_number', 'status', 'total_vouchers',
            'processed_vouchers', 'successful_vouchers', 'failed_vouchers',
            'started_at', 'completed_at', 'created_at', 'result_file_path',
            'brand_name', 'client_name', 'issued_by_username', 'issuer_type',
            'issuer_type_display', 'issuance_method', 'issuance_method_display',
            'denomination_breakdown'
        ]
        read_only_fields = fields


# ============================================================================
# REPORTING SERIALIZERS
# ============================================================================

class IssuanceReportItemSerializer(serializers.Serializer):
    """Serializer for issuance report item"""
    
    voucher_id = serializers.IntegerField()
    reference_number = serializers.CharField()
    voucher_code = serializers.CharField()
    brand_name = serializers.CharField()
    client_name = serializers.CharField(allow_null=True)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    status = serializers.CharField()
    issued_at = serializers.DateTimeField()
    created_by = serializers.CharField(allow_null=True)
    issued_by = serializers.CharField(allow_null=True)
    issuer_type = serializers.CharField(allow_null=True)


class IssuanceReportSerializer(serializers.Serializer):
    """Serializer for issuance report"""
    
    total_count = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    items = IssuanceReportItemSerializer(many=True)
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total_pages = serializers.IntegerField()


class RedemptionReportItemSerializer(serializers.Serializer):
    """Serializer for redemption report item"""
    
    transaction_id = serializers.IntegerField()
    voucher_code = serializers.CharField()
    reference_number = serializers.CharField()
    brand_name = serializers.CharField()
    redeemed_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    redemption_method = serializers.CharField()
    transaction_status = serializers.CharField()
    created_at = serializers.DateTimeField()


class RedemptionReportSerializer(serializers.Serializer):
    """Serializer for redemption report"""
    
    total_count = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    items = RedemptionReportItemSerializer(many=True)
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total_pages = serializers.IntegerField()


class OutstandingBalanceItemSerializer(serializers.Serializer):
    """Serializer for outstanding balance report item"""
    
    voucher_id = serializers.IntegerField()
    voucher_code = serializers.CharField()
    reference_number = serializers.CharField()
    brand_name = serializers.CharField()
    original_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    current_balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    redeemed_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    status = serializers.CharField()
    issued_at = serializers.DateTimeField()
    last_transaction_at = serializers.DateTimeField(allow_null=True)


class OutstandingBalanceReportSerializer(serializers.Serializer):
    """Serializer for outstanding balance report"""
    
    total_count = serializers.IntegerField()
    total_outstanding = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_issued = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_redeemed = serializers.DecimalField(max_digits=15, decimal_places=2)
    items = OutstandingBalanceItemSerializer(many=True)
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    total_pages = serializers.IntegerField()


# ============================================================================
# CLIENT MANAGEMENT SERIALIZERS
# ============================================================================

class VoucherClientSerializer(serializers.ModelSerializer):
    """Serializer for voucher client"""
    brand_name = serializers.CharField(source='brand.brand_name', read_only=True)
    
    class Meta:
        model = VoucherClient
        fields = [
            'id', 'brand', 'brand_name', 'client_name', 'client_code',
            'contact_person', 'contact_email', 'contact_phone',
            'is_default', 'status', 'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'client_code', 'created_at', 'updated_at']


class VoucherClientCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating voucher client"""
    
    class Meta:
        model = VoucherClient
        fields = [
            'brand', 'client_name', 'contact_person', 'contact_email',
            'contact_phone', 'is_default', 'status'
        ]
    
    def validate(self, attrs):
        """Validate client data"""
        brand = attrs.get('brand')
        is_default = attrs.get('is_default', False)
        
        if is_default:
            # Check if default client already exists for this brand
            existing_default = VoucherClient.objects.filter(
                brand=brand,
                is_default=True,
                status='ACTIVE'
            ).exclude(id=self.instance.id if self.instance else None)
            
            if existing_default.exists():
                raise serializers.ValidationError(
                    "Default client already exists for this brand"
                )
        
        return attrs


class VoucherClientListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for client list"""
    brand_name = serializers.CharField(source='brand.brand_name', read_only=True)
    
    class Meta:
        model = VoucherClient
        fields = [
            'id', 'client_name', 'client_code', 'brand_name',
            'is_default', 'status', 'created_at'
        ]
        read_only_fields = fields


# ============================================================================
# EXPORT SERIALIZERS
# ============================================================================

class BatchExportSerializer(serializers.Serializer):
    """Serializer for batch export request"""
    format = serializers.ChoiceField(choices=['csv', 'excel'], default='csv')
