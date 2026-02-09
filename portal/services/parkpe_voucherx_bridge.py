"""
ParkPe – VoucherX (Gift Voucher) bridge.
Replaces the old ParkPe balance service: voucher create = issue Gift Voucher (VoucherService);
balance = sum of user's Gift Vouchers; debit = redeem voucher by PIN.
Requires PARKPE_VOUCHER_BRAND_ID in config (or a GiftVoucherBrand with api_identifier 'PARKPE').
"""
from decimal import Decimal
from django.db.models import Sum

from portal.models import GiftVoucher, GiftVoucherBrand
from portal.services.voucher_service import VoucherService
from portal.utils.encryption import decrypt_data
from portal.utils.logging_helper import get_logger

logger = get_logger(__name__)


def get_parkpe_brand_id():
    """Resolve ParkPe voucher brand ID from config or by api_identifier. Returns None if not configured."""
    from core.config import payswap_config
    brand_id = getattr(payswap_config, "PARKPE_VOUCHER_BRAND_ID", None)
    if brand_id is not None:
        return int(brand_id)
    brand = GiftVoucherBrand.objects.filter(api_identifier__iexact="PARKPE").first()
    if brand:
        return brand.id
    return None


def _get_parkpe_brand_id():
    """Alias for get_parkpe_brand_id (internal use)."""
    return get_parkpe_brand_id()


def get_balance(user):
    """
    Return current voucher balance for ParkPe user = sum of current_balance of all
    Gift Vouchers issued for this user (metadata parkpe_user_id) with status ACTIVE or PARTIALLY_REDEEMED.
    """
    brand_id = _get_parkpe_brand_id()
    if not brand_id:
        return Decimal("0")
    result = (
        GiftVoucher.objects.filter(
            brand_id=brand_id,
            status__in=["ACTIVE", "PARTIALLY_REDEEMED"],
            metadata__parkpe_user_id=user.pk,
        ).aggregate(total=Sum("current_balance"))
    )
    total = result.get("total")
    return total if total is not None else Decimal("0")


def credit_voucher_balance(
    user,
    amount,
    reference_id=None,
    service_code="voucher_purchase",
    description=None,
):
    """
    Credit = issue a new Gift Voucher (VoucherX) for this user and amount.
    Uses VoucherService.issue_single_voucher with ParkPe brand; metadata stores parkpe_user_id.
    """
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("Credit amount must be positive")

    brand_id = _get_parkpe_brand_id()
    if not brand_id:
        raise ValueError(
            "ParkPe voucher brand not configured. Set PARKPE_VOUCHER_BRAND_ID or create a GiftVoucherBrand with api_identifier=PARKPE."
        )

    metadata = {"parkpe_user_id": user.pk}
    if reference_id:
        metadata["parkpe_reference_id"] = reference_id

    recipient_email = getattr(user, "email", None) or ""
    if not recipient_email and hasattr(user, "profile"):
        profile = getattr(user, "profile", None) or (getattr(user, "profile_set", None) and user.profile_set.first())
        if profile:
            recipient_email = getattr(profile, "email", None) or ""

    voucher_service = VoucherService()
    result = voucher_service.issue_single_voucher(
        brand_id=brand_id,
        amount=amount,
        mobile_number=getattr(user, "phone", None) or None,
        recipient_email=recipient_email or None,
        metadata=metadata,
        created_by=user,
        issued_by=user,
        issuer_type="API_PARTNER",
    )
    logger.info(
        "parkpe_voucherx_credit",
        extra_data={
            "user_id": user.pk,
            "amount": str(amount),
            "reference_id": reference_id,
            "voucher_id": result.get("voucher_id"),
        },
    )
    # Return (balance_obj_like, new_balance) for compatibility; we don't have balance_obj, so return (None, get_balance)
    return None, get_balance(user)


def debit_voucher_balance(
    user,
    amount,
    reference_id=None,
    service_code="BBPS",
    description=None,
):
    """
    Debit = redeem a Gift Voucher belonging to this user (by metadata parkpe_user_id).
    Picks a voucher with sufficient balance, decrypts PIN from metadata, and calls VoucherService.redeem_voucher_pin.
    """
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    if amount <= 0:
        raise ValueError("Debit amount must be positive")

    brand_id = _get_parkpe_brand_id()
    if not brand_id:
        raise ValueError("ParkPe voucher brand not configured.")

    # Find vouchers for this user with sufficient balance (oldest first)
    vouchers = (
        GiftVoucher.objects.filter(
            brand_id=brand_id,
            metadata__parkpe_user_id=user.pk,
            status__in=["ACTIVE", "PARTIALLY_REDEEMED"],
            current_balance__gte=amount,
        )
        .order_by("id")
    )
    voucher = vouchers.first()
    if not voucher:
        raise ValueError("Insufficient voucher balance.")

    pin = None
    if voucher.metadata and voucher.metadata.get("encrypted_pin"):
        try:
            pin = decrypt_data(voucher.metadata["encrypted_pin"])
        except Exception as e:
            logger.warning(
                "parkpe_voucherx_debit_pin_decrypt_failed",
                extra_data={"voucher_id": voucher.id, "error": str(e)},
            )
            raise ValueError("Cannot redeem voucher: PIN unavailable.") from e
    if not pin:
        raise ValueError("Cannot redeem voucher: PIN not found.")

    voucher_service = VoucherService()
    voucher_code = voucher.voucher_code
    if not voucher_code:
        raise ValueError("Cannot redeem voucher: code unavailable.")

    result = voucher_service.redeem_voucher_pin(
        voucher_code=voucher_code,
        pin=pin,
        amount=amount,
        transaction_ref=reference_id,
    )
    logger.info(
        "parkpe_voucherx_debit",
        extra_data={
            "user_id": user.pk,
            "amount": str(amount),
            "reference_id": reference_id,
            "voucher_id": voucher.id,
        },
    )
    new_balance = get_balance(user)
    return None, new_balance
