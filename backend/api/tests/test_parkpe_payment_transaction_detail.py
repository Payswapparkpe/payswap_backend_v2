"""
GET /api/payment/transactions/<id> must accept T-prefixed reference_ids (integer PK on ledger rows).
Using Q(pk=non_int) raises ValueError and became a 500 for receipt/history flows.
"""
from decimal import Decimal

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from portal.models import ParkPeVoucherTransaction, Profile, Role

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def parkpe_user(db):
    role, _ = Role.objects.get_or_create(
        code="customer",
        defaults={"name": "Customer", "category": "b2c", "hierarchy_level": 1},
    )
    user = User.objects.create_user(
        username="pp_txn_detail_u",
        password="parkpe_test_pass_123",
        role_code="customer",
        role=role,
        is_active=True,
    )
    Profile.objects.get_or_create(
        user=user,
        defaults={
            "first_name": "Txn",
            "last_name": "Detail",
            "email": "pp.txn.detail@example.com",
            "phone": "919876543299",
        },
    )
    return user


@pytest.mark.django_db
def test_transaction_detail_t_prefixed_reference_returns_200(api_client, parkpe_user):
    ref = "T202604161120315420P"
    ParkPeVoucherTransaction.objects.create(
        user=parkpe_user,
        amount=Decimal("10.00"),
        transaction_type=ParkPeVoucherTransaction.DEBIT,
        reference_id=ref,
        service_code="bbps",
        description="BBPS test",
    )
    login = api_client.post(
        "/api/auth/login",
        {"email": "pp.txn.detail@example.com", "password": "parkpe_test_pass_123"},
        format="json",
    )
    assert login.status_code == status.HTTP_200_OK, login.content
    token = login.json().get("token")
    assert token

    resp = api_client.get(
        f"/api/payment/transactions/{ref}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert resp.status_code == status.HTTP_200_OK, resp.content
    body = resp.json()
    assert body.get("transactionId") == ref
    assert body.get("amount") == 10.0
    assert body.get("customer", {}).get("name") == "Txn Detail"
    assert body.get("customer", {}).get("email") == "pp.txn.detail@example.com"
    assert "taxSnapshot" in body
    assert body["taxSnapshot"]["grandTotal"] == 10.0

    receipt = api_client.get(
        f"/api/payment/transactions/{ref}/receipt/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert receipt.status_code == status.HTTP_200_OK, receipt.content
    assert b"Bill to" in receipt.content or b"Taxable amount" in receipt.content


@pytest.mark.django_db
def test_transaction_detail_matches_legacy_billing_document_rows(api_client, parkpe_user):
    """
    Older BillingDocument rows may use different service_code casing, blank transaction_direction,
    or stale reference_id while still pointing at the voucher txn via FK — tax must still surface.
    """
    from portal.models import BillingDocument
    from portal.services.billing_document_service import record_billing_from_parkpe_voucher_transaction

    ref = "T209901011200009991Z"
    txn = ParkPeVoucherTransaction.objects.create(
        user=parkpe_user,
        amount=Decimal("25.00"),
        transaction_type=ParkPeVoucherTransaction.DEBIT,
        reference_id=ref,
        service_code="bbps",
        description="Legacy billing linkage",
    )
    record_billing_from_parkpe_voucher_transaction(txn)
    bd = BillingDocument.objects.filter(parkpe_voucher_transaction_id=txn.pk).first()
    assert bd
    BillingDocument.objects.filter(pk=bd.pk).update(
        transaction_direction="",
        service_code="BBPS",
        reference_id="stale-ref-not-matching-ledger",
    )

    login = api_client.post(
        "/api/auth/login",
        {"email": "pp.txn.detail@example.com", "password": "parkpe_test_pass_123"},
        format="json",
    )
    assert login.status_code == status.HTTP_200_OK
    token = login.json().get("token")

    resp = api_client.get(
        f"/api/payment/transactions/{ref}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert resp.status_code == status.HTTP_200_OK, resp.content
    body = resp.json()
    assert body.get("transactionId") == ref
    assert body.get("taxSnapshot", {}).get("grandTotal") == 25.0
