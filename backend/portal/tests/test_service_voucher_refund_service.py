from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from portal.models import ParkPeVoucherTransaction, Role, ServiceVoucherRefundCase, Vehicle
from portal.services.service_voucher_refund_service import (
    dismiss_service_voucher_refund_case,
    ensure_rc_view_refund_case,
)

User = get_user_model()


def _user(username: str, *, staff: bool = False):
    role, _ = Role.objects.get_or_create(
        code="customer",
        defaults={"name": "Customer", "category": "b2c"},
    )
    return User.objects.create_user(
        username=username,
        password="x",
        role=role,
        role_code=role.code,
        is_staff=staff,
    )


class ServiceVoucherRefundCaseTests(TestCase):
    def test_ensure_rc_view_refund_case_opens_row(self):
        user = _user("refund_u1")
        vehicle = Vehicle.objects.create(
            user=user,
            registration_number="MH01AB1111",
            vehicle_type="four_wheeler",
        )
        vehicle.rc_view_paid_at = timezone.now()
        vehicle.rc_view_debit_reference_id = "T_DEBIT_RC_1"
        vehicle.save(
            update_fields=["rc_view_paid_at", "rc_view_debit_reference_id", "registration_number_normalized"]
        )
        ParkPeVoucherTransaction.objects.create(
            user=user,
            amount=Decimal("50.00"),
            transaction_type=ParkPeVoucherTransaction.DEBIT,
            reference_id="T_DEBIT_RC_1",
            service_code="RC_VIEW",
            description="RC view – MH01AB1111",
        )
        case = ensure_rc_view_refund_case(
            vehicle=vehicle,
            rc_reason="http_error",
            customer_message="RC API returned an error.",
        )
        self.assertIsNotNone(case)
        self.assertEqual(case.status, ServiceVoucherRefundCase.STATUS_OPEN)
        self.assertEqual(case.debit_reference_id, "T_DEBIT_RC_1")
        self.assertEqual(case.amount, Decimal("50.00"))

    def test_dismiss_case(self):
        user = _user("refund_u2")
        admin = _user("refund_adm", staff=True)
        case = ServiceVoucherRefundCase.objects.create(
            user=user,
            debit_reference_id="T_X",
            amount=Decimal("50"),
            service_code="RC_VIEW",
            status=ServiceVoucherRefundCase.STATUS_OPEN,
            failure_detail="test",
        )
        dismiss_service_voucher_refund_case(case_id=case.pk, admin_user=admin, note="Not eligible — duplicate request.")
        case.refresh_from_db()
        self.assertEqual(case.status, ServiceVoucherRefundCase.STATUS_DISMISSED)
        self.assertEqual(case.dismissed_by_id, admin.pk)
