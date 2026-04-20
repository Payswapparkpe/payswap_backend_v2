"""Tax engine snapshot math and BillingDocument idempotency."""
import pytest
from decimal import Decimal

from django.contrib.auth import get_user_model

from portal.models import BillingDocument, Role, TaxServiceProfile
from portal.services.billing_document_service import record_billing_document
from portal.services.tax_engine import compute_tax_snapshot

User = get_user_model()


@pytest.mark.django_db
def test_compute_tax_snapshot_gst_inclusive_18_percent():
    TaxServiceProfile.objects.create(
        service_code="tax_test_svc",
        document_subtype=TaxServiceProfile.DOC_B2C,
        sac_or_hsn="999799",
        gst_rate=Decimal("18.0000"),
        gst_inclusive=True,
        is_gst_exempt=False,
        is_pass_through=False,
        tds_rate=None,
        is_active=True,
    )
    out = compute_tax_snapshot(
        service_code="tax_test_svc",
        document_subtype=TaxServiceProfile.DOC_B2C,
        amount=Decimal("118.00"),
        document_type=BillingDocument.DOC_B2C_RECEIPT,
    )
    assert out["taxable_amount"] == Decimal("100.00")
    assert out["gst_total"] == Decimal("18.00")
    assert out["cgst_amount"] == Decimal("9.00")
    assert out["sgst_amount"] == Decimal("9.00")
    assert out["grand_total"] == Decimal("118.00")


@pytest.mark.django_db
def test_compute_tax_snapshot_gst_exempt_value_of_supply_equals_amount():
    """Exempt / 0% B2C: full payment is value of supply; GST lines stay zero (clearer than taxable=0)."""
    TaxServiceProfile.objects.create(
        service_code="exempt_wallet_test",
        document_subtype=TaxServiceProfile.DOC_B2C,
        sac_or_hsn="",
        gst_rate=Decimal("0"),
        gst_inclusive=True,
        is_gst_exempt=True,
        is_pass_through=False,
        tds_rate=None,
        is_active=True,
    )
    out = compute_tax_snapshot(
        service_code="exempt_wallet_test",
        document_subtype=TaxServiceProfile.DOC_B2C,
        amount=Decimal("500.00"),
        document_type=BillingDocument.DOC_B2C_RECEIPT,
    )
    assert out["taxable_amount"] == Decimal("500.00")
    assert out["gst_total"] == Decimal("0")
    assert out["cgst_amount"] == Decimal("0")
    assert out["sgst_amount"] == Decimal("0")
    assert out["grand_total"] == Decimal("500.00")


@pytest.mark.django_db
def test_compute_tax_snapshot_pass_through_keeps_zero_taxable():
    TaxServiceProfile.objects.create(
        service_code="pass_through_test",
        document_subtype=TaxServiceProfile.DOC_B2C,
        sac_or_hsn="",
        gst_rate=Decimal("0"),
        gst_inclusive=True,
        is_gst_exempt=True,
        is_pass_through=True,
        tds_rate=None,
        is_active=True,
    )
    out = compute_tax_snapshot(
        service_code="pass_through_test",
        document_subtype=TaxServiceProfile.DOC_B2C,
        amount=Decimal("500.00"),
        document_type=BillingDocument.DOC_B2C_RECEIPT,
    )
    assert out["taxable_amount"] == Decimal("0")
    assert out["gst_total"] == Decimal("0")
    assert out["grand_total"] == Decimal("500.00")


@pytest.mark.django_db
def test_record_billing_document_idempotent():
    TaxServiceProfile.objects.create(
        service_code="idem_test_svc",
        document_subtype=TaxServiceProfile.DOC_B2C,
        gst_rate=Decimal("0"),
        gst_inclusive=True,
        is_gst_exempt=True,
        is_pass_through=False,
        is_active=True,
    )
    role, _ = Role.objects.get_or_create(
        code="customer",
        defaults={"name": "Customer", "category": "b2c", "hierarchy_level": 20},
    )
    user = User.objects.create_user(username="idem_u1", password="x", role_code=role.code)
    kwargs = dict(
        document_type=BillingDocument.DOC_B2C_RECEIPT,
        user=user,
        partner=None,
        service_code="idem_test_svc",
        reference_id="idem-ref-1",
        amount=Decimal("50.00"),
        parkpe_voucher_transaction_id=None,
        transaction_direction="debit",
    )
    a = record_billing_document(**kwargs)
    b = record_billing_document(**kwargs)
    assert a is not None and b is not None
    assert a.pk == b.pk
    assert BillingDocument.objects.filter(reference_id="idem-ref-1").count() == 1
