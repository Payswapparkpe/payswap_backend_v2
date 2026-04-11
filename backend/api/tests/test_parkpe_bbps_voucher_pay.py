from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from portal.models import Role, Profile

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def parkpe_customer(db):
    role, _ = Role.objects.get_or_create(
        code="customer",
        defaults={"name": "Customer", "category": "b2c", "hierarchy_level": 1},
    )
    user = User.objects.create_user(
        username="bbps_pay_user",
        password="bbps_test_pass_123",
        role_code="customer",
        role=role,
        is_active=True,
    )
    Profile.objects.get_or_create(
        user=user,
        defaults={
            "first_name": "BBPS",
            "last_name": "User",
            "email": "bbps.user@example.com",
            "phone": "919461001200",
        },
    )
    return user


@pytest.mark.django_db
def test_bbps_voucher_pay_uses_defined_descriptions_and_returns_success(api_client, parkpe_customer):
    """
    Regression test for NameError in voucher pay path:
    - description=bbps_pay_description
    - description=bbps_rollback_description
    Ensure debit ledger write uses defined constant and endpoint does not 500.
    """
    api_client.force_authenticate(user=parkpe_customer)

    voucher_stub = SimpleNamespace(
        id=1036,
        voucher_code="DE62AA8PAYLKJHNR",
        current_balance=Decimal("8600.00"),
        original_amount=Decimal("10000.00"),
    )

    payload = {
        "paymentMethod": "voucher",
        "billId": "T202603241218094219H",
        "operatorId": "CESU00000ODI01",
        "consumerId": "80003948751",
        "amount": 1400,
        "voucher_id": 1036,
        "pin": "1769",
    }

    with (
        patch("portal.services.parkpe_voucherx_bridge.get_parkpe_brand_id", return_value=1),
        patch("portal.models.GiftVoucher.objects.filter") as voucher_filter,
        patch("portal.services.voucher_service.VoucherService.verify_pin", return_value=(True, None)),
        patch("portal.services.voucher_service.VoucherService.redeem_voucher_pin", return_value=True),
        patch("api.bbps_parkpe.views.BBPSService.is_available", return_value=True),
        patch(
            "api.bbps_parkpe.views.BBPSService.pay_bill",
            return_value={"success": True, "transaction_id": payload["billId"], "status": "SUBMITTED", "vendor": "mobikwik"},
        ),
        patch("portal.models.ParkPeVoucherTransaction.objects.create") as pp_txn_create,
        patch("portal.services.hub_income_service.record_hub_income", return_value=None),
    ):
        voucher_filter.return_value.first.return_value = voucher_stub
        response = api_client.post("/api/bbps/pay", payload, format="json")

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["success"] is True
    assert body["transactionId"] == payload["billId"]

    # Debit ledger insert should use stable, defined description text.
    pp_txn_create.assert_called()
    create_kwargs = pp_txn_create.call_args.kwargs
    assert create_kwargs["service_code"] == "BBPS"
    assert create_kwargs["transaction_type"] == "debit"
    assert create_kwargs["description"] == "BBPS voucher bill payment"
