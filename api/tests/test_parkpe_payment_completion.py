"""
ParkPe PG completion: idempotent voucher credit (webhook + verify must not double-credit).

Row-level lock (SELECT FOR UPDATE) prevents concurrent completions; this test asserts the
second completion is a no-op when the order is already completed.
"""
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from api.parkpe_api.views import _complete_parkpe_payment_order
from portal.models import ParkPePaymentOrder, Role

User = get_user_model()


@pytest.fixture
def parkpe_role(db):
    role, _ = Role.objects.get_or_create(
        code="customer",
        defaults={"name": "Customer", "category": "b2c", "hierarchy_level": 1},
    )
    return role


@pytest.mark.django_db
def test_complete_parkpe_payment_order_credits_once_on_repeat_call(parkpe_role):
    """Second completion for the same order must not call credit again (simulates webhook + verify)."""
    user = User.objects.create_user(
        username="pp_cc_u1",
        password="test-pass-12345",
        role_code="customer",
        role=parkpe_role,
        is_active=True,
    )
    order = ParkPePaymentOrder.objects.create(
        user=user,
        amount=Decimal("100.00"),
        gateway="cashfree",
        order_id="test_order_idem_1",
        status=ParkPePaymentOrder.PENDING,
        metadata={},
    )

    with patch("api.parkpe_api.views.credit_voucher_balance") as mock_credit:
        _complete_parkpe_payment_order(order, payment_id="pay_test_1", request=None)
        assert mock_credit.call_count == 1
        # Stale in-memory order still pending; DB row is completed — must not double-credit
        _complete_parkpe_payment_order(order, payment_id="pay_test_2", request=None)
        assert mock_credit.call_count == 1

    order.refresh_from_db()
    assert order.status == ParkPePaymentOrder.COMPLETED
