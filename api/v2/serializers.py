"""
Serializers for API v2 (External Partners)
"""
from rest_framework import serializers
from decimal import Decimal
from portal.models import (
    GiftVoucher, GiftVoucherTransaction, BulkVoucherIssuanceBatch,
    GiftVoucherBrand
)


# ============================================================================
# VOUCHER ISSUANCE SERIALIZERS
# ============================================================================

class VoucherIssueSerializer(serializers.Serializer):
    """Serializer for single voucher issuance via API. email is required.
    Brand identify: api_identifier (6-char alphanumeric, recommended) YA brand_id YA brand_code – ek zaroor.
    """

    api_identifier = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=6,
        min_length=6,
        help_text="6-char alphanumeric unique code (brand onboard hote hi auto-generate). Recommended."
    )
    brand_id = serializers.IntegerField(required=False, allow_null=True)
    brand_code = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=20)
    client_id = serializers.IntegerField(required=False, allow_null=True)
    amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=True,
        min_value=Decimal('0.01')
    )
    email = serializers.EmailField(
        required=True,
        help_text="Recipient email (required for API single voucher issuance)"
    )
    mobile_number = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        allow_null=True
    )
    metadata = serializers.JSONField(required=False, default=dict)

    def validate(self, attrs):
        """Brand identify: api_identifier (6-char) YA brand_id YA brand_code – sirf ek bhejein."""
        api_identifier = (attrs.get('api_identifier') or '').strip().upper()
        brand_id = attrs.get('brand_id')
        brand_code = (attrs.get('brand_code') or '').strip()
        provided = sum(bool(api_identifier), bool(brand_id), bool(brand_code))
        if provided == 0:
            raise serializers.ValidationError({
                'brand': 'Brand identify karne ke liye api_identifier (6-char), brand_id ya brand_code mein se ek bhejen.'
            })
        if provided > 1:
            raise serializers.ValidationError({
                'brand': 'Sirf ek bhejen: api_identifier ya brand_id ya brand_code.'
            })
        if api_identifier:
            attrs['api_identifier'] = api_identifier
        return attrs


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


class BulkVoucherIssueSerializer(serializers.Serializer):
    """Serializer for bulk voucher issuance"""
    
    brand_id = serializers.IntegerField(required=True)
    client_id = serializers.IntegerField(required=False, allow_null=True)
    denominations = serializers.DictField(
        child=serializers.DictField(
            child=serializers.IntegerField()
        ),
        required=True,
        help_text="Dict of {amount: {quantity: count}}"
    )


class BulkVoucherIssueResponseSerializer(serializers.Serializer):
    """Response serializer for bulk issuance"""
    
    batch_id = serializers.IntegerField()
    batch_reference = serializers.CharField()
    total_vouchers = serializers.IntegerField()
    status = serializers.CharField()
    status_url = serializers.CharField()


# ============================================================================
# VOUCHER REDEMPTION SERIALIZERS
# ============================================================================

class VoucherRedeemPINSerializer(serializers.Serializer):
    """Serializer for PIN-based redemption"""
    
    voucher_code = serializers.CharField(required=True, max_length=25)
    pin = serializers.CharField(required=True, max_length=4, min_length=4)
    amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        allow_null=True,
        help_text="Amount to redeem (null = full balance)"
    )


class VoucherRedeemOTPRequestSerializer(serializers.Serializer):
    """Serializer for OTP redemption request"""
    
    voucher_code = serializers.CharField(required=True, max_length=25)
    mobile_number = serializers.CharField(required=True, max_length=20)


class VoucherRedeemOTPVerifySerializer(serializers.Serializer):
    """Serializer for OTP verification and redemption"""
    
    voucher_code = serializers.CharField(required=True, max_length=25)
    otp = serializers.CharField(required=True, max_length=6, min_length=6)
    amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        allow_null=True,
        help_text="Amount to redeem (null = full balance)"
    )


# ============================================================================
# VOUCHER BALANCE SERIALIZERS
# ============================================================================

class VoucherBalanceSerializer(serializers.Serializer):
    """Serializer for balance check request"""
    
    voucher_code = serializers.CharField(required=True, max_length=25)


class VoucherBalanceResponseSerializer(serializers.Serializer):
    """Response serializer for balance check"""
    
    voucher_code = serializers.CharField()
    reference_number = serializers.CharField()
    original_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    current_balance = serializers.DecimalField(max_digits=15, decimal_places=2)
    currency = serializers.CharField()
    status = serializers.CharField()
    brand_name = serializers.CharField(allow_null=True)
    issued_at = serializers.DateTimeField()


# ============================================================================
# VOUCHER PIN CHANGE SERIALIZERS
# ============================================================================

class VoucherPINChangeRequestSerializer(serializers.Serializer):
    """Serializer for PIN change OTP request"""
    
    mobile_number = serializers.CharField(required=True, max_length=20)


class VoucherPINChangeVerifySerializer(serializers.Serializer):
    """Serializer for PIN change verification"""
    
    otp = serializers.CharField(required=True, max_length=6, min_length=6)
    new_pin = serializers.CharField(required=True, max_length=4, min_length=4)


# ============================================================================
# BATCH SERIALIZERS
# ============================================================================

class VoucherBatchListSerializer(serializers.ModelSerializer):
    """Serializer for batch list"""
    
    class Meta:
        model = BulkVoucherIssuanceBatch
        fields = [
            'id', 'batch_reference', 'total_vouchers',
            'processed_vouchers', 'successful_vouchers', 'failed_vouchers',
            'status', 'created_at', 'started_at', 'completed_at'
        ]


class VoucherBatchDetailSerializer(serializers.ModelSerializer):
    """Serializer for batch details"""
    
    brand_name = serializers.CharField(source='brand.brand_name', read_only=True)
    
    class Meta:
        model = BulkVoucherIssuanceBatch
        fields = [
            'id', 'batch_reference', 'batch_reference_number',
            'total_vouchers', 'processed_vouchers', 'successful_vouchers',
            'failed_vouchers', 'status', 'issuance_method',
            'denomination_breakdown', 'created_at', 'started_at',
            'completed_at', 'brand_name'
        ]


# ============================================================================
# KYC/VERIFICATION SERIALIZERS
# ============================================================================

class PANVerifySerializer(serializers.Serializer):
    """Serializer for PAN verification"""
    pan_number = serializers.CharField(required=True, max_length=10, min_length=10)


class AadhaarVerifySerializer(serializers.Serializer):
    """Serializer for Aadhaar verification"""
    aadhaar_number = serializers.CharField(required=True, max_length=12, min_length=12)


class BankVerifySerializer(serializers.Serializer):
    """Serializer for bank account verification"""
    account_number = serializers.CharField(required=True, max_length=20)
    ifsc_code = serializers.CharField(required=True, max_length=11)
    account_holder_name = serializers.CharField(required=False, max_length=255)


class DrivingLicenseVerifySerializer(serializers.Serializer):
    """Serializer for driving license verification"""
    dl_number = serializers.CharField(required=True, max_length=20)
    dob = serializers.DateField(required=False, allow_null=True)
    document_file = serializers.FileField(required=False, allow_null=True)
    document_base64 = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class VoterIDVerifySerializer(serializers.Serializer):
    """Serializer for voter ID verification"""
    voter_id_number = serializers.CharField(required=True, max_length=20)
    document_file = serializers.FileField(required=False, allow_null=True)
    document_base64 = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class PassportVerifySerializer(serializers.Serializer):
    """Serializer for passport verification"""
    passport_number = serializers.CharField(required=True, max_length=20)
    document_file = serializers.FileField(required=False, allow_null=True)
    document_base64 = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class GSTVerifySerializer(serializers.Serializer):
    """Serializer for GST verification"""
    gst_number = serializers.CharField(required=True, max_length=15)


class FaceMatchSerializer(serializers.Serializer):
    """Serializer for face matching"""
    image1_file = serializers.FileField(required=False, allow_null=True)
    image2_file = serializers.FileField(required=False, allow_null=True)
    image1_base64 = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    image2_base64 = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class FaceLivenessSerializer(serializers.Serializer):
    """Serializer for face liveness check"""
    image_file = serializers.FileField(required=False, allow_null=True)
    image_base64 = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class VerificationStatusSerializer(serializers.Serializer):
    """Serializer for verification status response"""
    verification_id = serializers.CharField()
    status = serializers.CharField()
    result = serializers.JSONField(allow_null=True)
    error_message = serializers.CharField(allow_null=True, allow_blank=True)


# ============================================================================
# PAYMENT SERIALIZERS
# ============================================================================

class PaymentInitiateSerializer(serializers.Serializer):
    """Serializer for payment initiation"""
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=True, min_value=Decimal('0.01'))
    currency = serializers.CharField(max_length=3, default='INR', required=False)
    order_id = serializers.CharField(max_length=100, required=False, allow_null=True)
    customer_name = serializers.CharField(max_length=255, required=False)
    customer_email = serializers.EmailField(required=False, allow_null=True)
    customer_phone = serializers.CharField(max_length=20, required=False, allow_null=True)
    return_url = serializers.URLField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False, default=dict)


class PaymentStatusSerializer(serializers.Serializer):
    """Serializer for payment status response"""
    payment_id = serializers.CharField()
    status = serializers.CharField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    currency = serializers.CharField()
    order_id = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)


class PaymentRefundSerializer(serializers.Serializer):
    """Serializer for payment refund"""
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False, allow_null=True, help_text="Refund amount (null = full refund)")
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class PaymentListSerializer(serializers.Serializer):
    """Serializer for payment list response"""
    payment_id = serializers.CharField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    currency = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


# ============================================================================
# SMS SERIALIZERS
# ============================================================================

class SMSSendSerializer(serializers.Serializer):
    """Serializer for SMS sending"""
    phone_number = serializers.CharField(required=True, max_length=20)
    message = serializers.CharField(required=True, max_length=1600)


class SMSOTPSendSerializer(serializers.Serializer):
    """Serializer for OTP sending"""
    phone_number = serializers.CharField(required=True, max_length=20)


class SMSOTPVerifySerializer(serializers.Serializer):
    """Serializer for OTP verification"""
    phone_number = serializers.CharField(required=True, max_length=20)
    otp_code = serializers.CharField(required=True, max_length=6, min_length=6)


class SMSDeliveryStatusSerializer(serializers.Serializer):
    """Serializer for SMS delivery status response"""
    message_id = serializers.CharField()
    status = serializers.CharField()
    delivered_at = serializers.DateTimeField(allow_null=True)


# ============================================================================
# BBPS (Bharat Bill Payment System) SERIALIZERS
# ============================================================================

class BBPSOperatorsSerializer(serializers.Serializer):
    """Query params for operators list"""
    category = serializers.CharField(required=False, allow_blank=True, max_length=50)


class BBPSFetchBillSerializer(serializers.Serializer):
    """Serializer for BBPS bill fetch. vendor: euronet | mobikwik (optional, default mobikwik)."""
    operator_id = serializers.CharField(required=True, max_length=100)
    customer_id = serializers.CharField(required=True, max_length=100)
    subscriber_id = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=100)
    vendor = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=32)
    ad1 = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=200)
    ad2 = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=200)
    ad3 = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=200)
    ad4 = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=200)
    ad9 = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=200)


class BBPSPayBillSerializer(serializers.Serializer):
    """Serializer for BBPS bill payment. vendor: euronet | mobikwik (optional, default mobikwik)."""
    operator_id = serializers.CharField(required=True, max_length=100)
    customer_id = serializers.CharField(required=True, max_length=100)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=True, min_value=Decimal('0.01'))
    ref_id = serializers.CharField(required=True, max_length=64)
    subscriber_id = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=100)
    vendor = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=32)
    ad1 = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=200)
    ad2 = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=200)
    ad3 = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=200)
    ad4 = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=200)
    ad9 = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=200)


# ============================================================================
# AEPS (PayPoint) SERIALIZERS
# ============================================================================

class AEPSBalanceEnquirySerializer(serializers.Serializer):
    """Serializer for AEPS balance enquiry"""
    aadhaar_number = serializers.CharField(required=True, max_length=12, min_length=12)
    mobile_number = serializers.CharField(required=True, max_length=10, min_length=10)
    bank_iin = serializers.CharField(required=True, max_length=20)
    rd_request = serializers.CharField(required=True, help_text='Biometric PID/XML from certified device')
    latitude = serializers.CharField(required=True, max_length=20)
    longitude = serializers.CharField(required=True, max_length=20)
    terminal_id = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)


class AEPSCashWithdrawalSerializer(serializers.Serializer):
    """Serializer for AEPS cash withdrawal"""
    aadhaar_number = serializers.CharField(required=True, max_length=12, min_length=12)
    mobile_number = serializers.CharField(required=True, max_length=10, min_length=10)
    bank_iin = serializers.CharField(required=True, max_length=20)
    rd_request = serializers.CharField(required=True, help_text='Biometric PID/XML from certified device')
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=True, min_value=Decimal('1'))
    latitude = serializers.CharField(required=True, max_length=20)
    longitude = serializers.CharField(required=True, max_length=20)
    terminal_id = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)
    client_ref_id = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=64)


class AEPSMiniStatementSerializer(serializers.Serializer):
    """Serializer for AEPS mini statement"""
    aadhaar_number = serializers.CharField(required=True, max_length=12, min_length=12)
    mobile_number = serializers.CharField(required=True, max_length=10, min_length=10)
    bank_iin = serializers.CharField(required=True, max_length=20)
    rd_request = serializers.CharField(required=True, help_text='Biometric PID/XML from certified device')
    latitude = serializers.CharField(required=True, max_length=20)
    longitude = serializers.CharField(required=True, max_length=20)
    terminal_id = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)


class AEPSAgentRegistrationSerializer(serializers.Serializer):
    """Serializer for PayPoint AEPS Agent Registration"""
    agent_name = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=100)
    mobile_number = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=15)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True, max_length=100)


class AEPSUpdateAgentDetailsSerializer(serializers.Serializer):
    """Serializer for PayPoint AEPS Update Agent Details"""
    agent_id = serializers.CharField(required=True, max_length=64)
    agent_name = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=100)
    mobile_number = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=15)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True, max_length=100)


class AEPSAgentServiceStatusSerializer(serializers.Serializer):
    """Serializer for PayPoint AEPS Check Agent Service Status"""
    agent_id = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=64)


class AEPSAgentAuthenticationSerializer(serializers.Serializer):
    """Serializer for PayPoint AEPS Check Agent Authentication"""
    agent_id = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=64)


class AEPSTwoFactorAuthenticationSerializer(serializers.Serializer):
    """Serializer for PayPoint AEPS Two Factor Authentication"""
    otp = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=10)
    mobile_number = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=15)


# ============================================================================
# DMT (PayPoint Domestic Money Transfer) SERIALIZERS
# ============================================================================

class DMTRegisterSenderSerializer(serializers.Serializer):
    """Serializer for PayPoint DMT sender/remitter registration"""
    mobile_number = serializers.CharField(required=True, max_length=15)
    first_name = serializers.CharField(required=True, max_length=100)
    last_name = serializers.CharField(required=True, max_length=100)
    pincode = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=10)
    state = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=50)
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    date_of_birth = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=20)


class DMTAddBeneficiarySerializer(serializers.Serializer):
    """Serializer for PayPoint DMT add beneficiary"""
    sender_mobile = serializers.CharField(required=True, max_length=15)
    beneficiary_name = serializers.CharField(required=True, max_length=100)
    account_number = serializers.CharField(required=True, max_length=34)
    ifsc = serializers.CharField(required=True, max_length=11)
    mobile_number = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=15)
    bank_name = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=100)


class DMTRemitSerializer(serializers.Serializer):
    """Serializer for PayPoint DMT remit"""
    sender_mobile = serializers.CharField(required=True, max_length=15)
    beneficiary_id = serializers.CharField(required=True, max_length=64)
    amount = serializers.CharField(required=True, max_length=20)
    client_ref_id = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=64)
    remarks = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=200)


class DMTGetBeneficiariesSerializer(serializers.Serializer):
    """Serializer for PayPoint DMT get beneficiaries"""
    sender_mobile = serializers.CharField(required=True, max_length=15)
