"""
Central API registry for vendor/service action mappings.

This module is the single place for:
- service_name + required_action -> canonical vendor api_code(s)
- view module -> likely vendor hints
- orchestration handler registration lists
"""

from typing import List


SERVICE_ACTION_TO_API_CODES = {
    "bbps": {
        "operators": ["operators"],
        "fetch_bill": ["fetch_bill"],
        "pay_bill": ["pay_bill"],
        "payment_status": ["payment_status"],
    },
    "kyc": {
        "pan": ["pan"],
        "aadhaar": ["aadhaar"],
        "bank": ["bank"],
        "gst": ["gst"],
        "driving_license": ["driving_license"],
        "voter_id": ["voter_id"],
        "passport": ["passport"],
        "face_match": ["face_match"],
        "face_liveness": ["face_liveness"],
        "status": ["status"],
    },
    "sms": {
        "send": ["sms"],
        "otp_send": ["sms"],
        "otp_verify": ["sms"],
        "delivery_status": ["sms"],
    },
    "payment": {
        "initiate": ["create_order"],
        "status": ["order_status"],
        "refund": ["refund"],
    },
    "aeps": {
        "withdraw": ["aeps_withdraw"],
        "balance_check": ["balance_check"],
        "account_statement": ["account_statement"],
    },
    "dmt": {
        "transfer": ["dmt_transfer"],
        "remittance_domestic": ["remittance_domestic"],
        "remittance_nepal": ["remittance_nepal"],
    },
    "billpay": {
        "credit_card_pay": ["credit_card_bill_pay"],
    },
    "vehicle": {
        "rc_verify": ["rc_verification"],
        "challan_lookup": ["vehicle_challan_lookup"],
    },
    "identity_docs": {
        "digilocker_init": ["digilocker_init"],
    },
    "cards": {
        "bin_lookup": ["card_bin_lookup"],
    },
    "credit": {
        "report": ["credit_report"],
        "score_simulator": ["credit_score_simulator"],
    },
    "merchant": {
        "onboarding": ["merchant_onboarding"],
    },
    "reconciliation": {
        "transaction_status": ["transaction_status"],
    },
}


VIEW_MODULE_VENDOR_HINTS = {
    ".instantpay_views": ["instantpay"],
    ".bbps_views": ["mobikwik", "euronet"],
    ".kyc_views": ["cashfree", "leegality"],
    ".sms_views": ["kaleyra"],
    ".payment_views": ["cashfree_pg"],
}


INSTANTPAY_HANDLER_API_CODES = [
    "aeps_withdraw",
    "balance_check",
    "account_statement",
    "dmt_transfer",
    "remittance_domestic",
    "remittance_nepal",
    "credit_card_bill_pay",
    "rc_verification",
    "vehicle_challan_lookup",
    "digilocker_init",
    "digilocker_status",
    "card_bin_lookup",
    "credit_report",
    "credit_score_simulator",
    "merchant_onboarding",
    "transaction_status",
    "gstin_lookup",
    "pincode_lookup",
    "bank_verification",
]

API_RUNTIME_TOKEN_HINTS = {
    # Kaleyra OTP/SMS traffic often comes via auth/parkpe endpoints too.
    "sms": [
        "sms/send",
        "sms/otp/send",
        "sms/otp/verify",
        "sms/delivery-status",
        "auth/otp/request",
        "auth/otp/verify",
        "otp request sent",
        "otp verify success",
        "otp_send_attempt",
        "otp_sent_success",
        "otp_sms_task",
        "kaleyra_otp_response",
        "kaleyra_sms_response",
    ],
    "click_to_call": [
        "click_to_call",
        "click-to-call",
        "connect/call",
        "connect_call",
    ],
    "template_sms": [
        "template_sms",
        "template sms",
        "kaleyra_template_sms",
    ],
}


def infer_vendor_hints_for_view_module(module_name: str) -> List[str]:
    module_name = (module_name or "").lower()
    for suffix, vendors in VIEW_MODULE_VENDOR_HINTS.items():
        if module_name.endswith(suffix):
            return list(vendors)
    return []


def resolve_api_codes_for_view(view_cls) -> List[str]:
    """
    Resolve canonical api_code list for a DRF view class.
    """
    api_codes: List[str] = []

    direct_api_code = getattr(view_cls, "api_code", None)
    if direct_api_code:
        api_codes.append(direct_api_code)

    if view_cls.__name__ == "TransactionStatusView" and "transaction_status" not in api_codes:
        api_codes.append("transaction_status")

    service_name = (getattr(view_cls, "service_name", "") or "").strip().lower()
    required_action = (getattr(view_cls, "required_action", "") or "").strip().lower()
    for code in SERVICE_ACTION_TO_API_CODES.get(service_name, {}).get(required_action, []):
        if code not in api_codes:
            api_codes.append(code)

    return api_codes


def runtime_token_hints_for_api(api_code: str) -> List[str]:
    """
    Extra token hints used by /services runtime metrics matching.
    """
    return list(API_RUNTIME_TOKEN_HINTS.get((api_code or "").strip().lower(), []))
