"""
API Version 2 URL Configuration - External Parties
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HealthCheckView
from .voucher_views import (
    VoucherIssueView, BulkVoucherIssueView, VoucherRedeemPINView,
    VoucherRedeemOTPRequestView, VoucherRedeemOTPVerifyView,
    VoucherBalanceView, VoucherPINChangeRequestView, VoucherPINChangeVerifyView,
    VoucherBatchListView, VoucherBatchDetailView
)
from .kyc_views import (
    PANVerifyView, AadhaarVerifyView, BankVerifyView,
    DrivingLicenseVerifyView, VoterIDVerifyView, PassportVerifyView,
    GSTVerifyView, FaceMatchView, FaceLivenessView, VerificationStatusView
)
from .payment_views import (
    PaymentInitiateView, PaymentStatusView, PaymentRefundView, PaymentListView
)
from .sms_views import (
    SMSSendView, SMSOTPSendView, SMSOTPVerifyView, SMSDeliveryStatusView
)
from .bbps_views import (
    BBPSOperatorsView, BBPSFetchBillView, BBPSPayBillView, BBPSPaymentStatusView
)
from .service_flow_views import (
    VendorListView,
    VendorDetailView,
    ServiceListView,
    ServiceFlowView,
)
from .instantpay_views import (
    AepsWithdrawView,
    AepsBalanceCheckView,
    AepsAccountStatementView,
    DmtTransferView,
    DomesticRemittanceView,
    NepalRemittanceView,
    CreditCardBillPayView,
    RcVerificationView,
    VehicleChallanLookupView,
    DigiLockerInitView,
    BinLookupView,
    CreditReportView,
    CreditScoreSimulatorView,
    MerchantOnboardingView,
    TransactionStatusView,
)

router = DefaultRouter()
# Register external ViewSets here: router.register(r'resource', ViewSet, basename='resource')

urlpatterns = [
    # Public endpoints
    path("health/", HealthCheckView.as_view(), name="health-check"),
    
    # Voucher Management APIs
    path("vouchers/issue/", VoucherIssueView.as_view(), name="v2-voucher-issue"),
    path("vouchers/bulk-issue/", BulkVoucherIssueView.as_view(), name="v2-voucher-bulk-issue"),
    path("vouchers/redeem-pin/", VoucherRedeemPINView.as_view(), name="v2-voucher-redeem-pin"),
    path("vouchers/redeem-otp/request/", VoucherRedeemOTPRequestView.as_view(), name="v2-voucher-redeem-otp-request"),
    path("vouchers/redeem-otp/verify/", VoucherRedeemOTPVerifyView.as_view(), name="v2-voucher-redeem-otp-verify"),
    path("vouchers/<str:voucher_code>/balance/", VoucherBalanceView.as_view(), name="v2-voucher-balance"),
    path("vouchers/<str:voucher_code>/pin/change/request/", VoucherPINChangeRequestView.as_view(), name="v2-voucher-pin-change-request"),
    path("vouchers/<str:voucher_code>/pin/change/verify/", VoucherPINChangeVerifyView.as_view(), name="v2-voucher-pin-change-verify"),
    path("vouchers/batches/", VoucherBatchListView.as_view(), name="v2-voucher-batches"),
    path("vouchers/batches/<int:batch_id>/", VoucherBatchDetailView.as_view(), name="v2-voucher-batch-detail"),
    
    # KYC/Verification APIs
    path("kyc/pan/verify/", PANVerifyView.as_view(), name="v2-kyc-pan-verify"),
    path("kyc/aadhaar/verify/", AadhaarVerifyView.as_view(), name="v2-kyc-aadhaar-verify"),
    path("kyc/bank/verify/", BankVerifyView.as_view(), name="v2-kyc-bank-verify"),
    path("kyc/driving-license/verify/", DrivingLicenseVerifyView.as_view(), name="v2-kyc-driving-license-verify"),
    path("kyc/voter-id/verify/", VoterIDVerifyView.as_view(), name="v2-kyc-voter-id-verify"),
    path("kyc/passport/verify/", PassportVerifyView.as_view(), name="v2-kyc-passport-verify"),
    path("kyc/gst/verify/", GSTVerifyView.as_view(), name="v2-kyc-gst-verify"),
    path("kyc/face-match/", FaceMatchView.as_view(), name="v2-kyc-face-match"),
    path("kyc/face-liveness/", FaceLivenessView.as_view(), name="v2-kyc-face-liveness"),
    path("kyc/verifications/<str:verification_id>/", VerificationStatusView.as_view(), name="v2-kyc-verification-status"),
    
    # Payment Gateway APIs
    path("payments/initiate/", PaymentInitiateView.as_view(), name="v2-payment-initiate"),
    path("payments/<str:payment_id>/status/", PaymentStatusView.as_view(), name="v2-payment-status"),
    path("payments/<str:payment_id>/refund/", PaymentRefundView.as_view(), name="v2-payment-refund"),
    path("payments/", PaymentListView.as_view(), name="v2-payment-list"),
    
    # SMS/OTP APIs
    path("sms/send/", SMSSendView.as_view(), name="v2-sms-send"),
    path("sms/otp/send/", SMSOTPSendView.as_view(), name="v2-sms-otp-send"),
    path("sms/otp/verify/", SMSOTPVerifyView.as_view(), name="v2-sms-otp-verify"),
    path("sms/delivery-status/<str:message_id>/", SMSDeliveryStatusView.as_view(), name="v2-sms-delivery-status"),
    
    # BBPS (Mobikwik) APIs
    path("bbps/operators/", BBPSOperatorsView.as_view(), name="v2-bbps-operators"),
    path("bbps/bill/fetch/", BBPSFetchBillView.as_view(), name="v2-bbps-fetch-bill"),
    path("bbps/bill/pay/", BBPSPayBillView.as_view(), name="v2-bbps-pay-bill"),
    path("bbps/bill/status/<str:ref_id>/", BBPSPaymentStatusView.as_view(), name="v2-bbps-payment-status"),

    # Instantpay Modules
    path("aeps/withdraw/", AepsWithdrawView.as_view(), name="v2-aeps-withdraw"),
    path("aeps/balance-check/", AepsBalanceCheckView.as_view(), name="v2-aeps-balance-check"),
    path("aeps/account-statement/", AepsAccountStatementView.as_view(), name="v2-aeps-account-statement"),
    path("dmt/transfer/", DmtTransferView.as_view(), name="v2-dmt-transfer"),
    path("dmt/remittance/domestic/", DomesticRemittanceView.as_view(), name="v2-remittance-domestic"),
    path("dmt/remittance/nepal/", NepalRemittanceView.as_view(), name="v2-remittance-nepal"),
    path("billpay/credit-card/pay/", CreditCardBillPayView.as_view(), name="v2-credit-card-billpay"),
    path("vehicle/rc-verify/", RcVerificationView.as_view(), name="v2-vehicle-rc-verify"),
    path("vehicle/challan-lookup/", VehicleChallanLookupView.as_view(), name="v2-vehicle-challan-lookup"),
    path("identity-docs/digilocker/init/", DigiLockerInitView.as_view(), name="v2-digilocker-init"),
    path("cards/bin-lookup/", BinLookupView.as_view(), name="v2-bin-lookup"),
    path("credit/report/", CreditReportView.as_view(), name="v2-credit-report"),
    path("credit/score-simulator/", CreditScoreSimulatorView.as_view(), name="v2-credit-score-simulator"),
    path("merchant/onboarding/", MerchantOnboardingView.as_view(), name="v2-merchant-onboarding"),
    path("reconciliation/transaction-status/<str:partner_txn_id>/", TransactionStatusView.as_view(), name="v2-transaction-status"),
    
    # Vendor-orchestrated service flows (vendors, APIs, ordered steps)
    path("vendors/", VendorListView.as_view(), name="v2-vendors-list"),
    path("vendors/<str:vendor_code>/", VendorDetailView.as_view(), name="v2-vendor-detail"),
    path("services/", ServiceListView.as_view(), name="v2-services-list"),
    path("services/<str:service_code>/flow/", ServiceFlowView.as_view(), name="v2-service-flow"),
    
    # Router URLs
    path("", include(router.urls)),
]
