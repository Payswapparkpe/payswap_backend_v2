"""
ParkPe voucher claim API and bulk mobile → parkpe_user_id helper.
"""
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from portal.models import Role, Profile, GiftVoucherBrand
from portal.services.voucher_service import VoucherService
from portal.tasks.voucher_tasks import _resolve_parkpe_user_id_from_mobile

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


def _unique_username(prefix: str) -> str:
    import uuid

    return f"{prefix}{uuid.uuid4().hex[:8]}"[:15]


def _customer(role_code="customer", phone="+919876543210"):
    role, _ = Role.objects.get_or_create(
        code=role_code,
        defaults={"name": "Customer", "category": "b2c", "hierarchy_level": 1},
    )
    u = User.objects.create_user(
        username=_unique_username("cu"),
        password="test_pass_claim_1",
        role_code=role_code,
        role=role,
        is_active=True,
    )
    Profile.objects.get_or_create(
        user=u,
        defaults={
            "first_name": "Claim",
            "last_name": "User",
            "email": f"{u.username}@example.com",
            "phone": phone,
        },
    )
    return u


def _other_customer():
    role, _ = Role.objects.get_or_create(
        code="customer",
        defaults={"name": "Customer", "category": "b2c", "hierarchy_level": 1},
    )
    u = User.objects.create_user(
        username=_unique_username("ot"),
        password="test_pass_claim_2",
        role_code="customer",
        role=role,
        is_active=True,
    )
    Profile.objects.get_or_create(
        user=u,
        defaults={
            "first_name": "Other",
            "last_name": "User",
            "email": f"{u.username}@example.com",
            "phone": "+919988776655",
        },
    )
    return u


def _parkpe_brand():
    """Brand used when get_parkpe_brand_id is patched to return its id."""
    n = abs(hash("parkpe_claim_brand")) % 100000
    return GiftVoucherBrand.objects.create(
        brand_code=f"PK{n}"[:20],
        brand_name="ParkPe Claim Test",
        api_identifier=f"P{n}"[:6],
        status="ACTIVE",
        onboarding_status="APPROVED",
    )


@pytest.mark.django_db
def test_claim_success_sets_parkpe_user_id(api_client):
    issuer = _customer(phone="+919000000010")
    owner2 = _customer(phone="+919111222333")

    brand = _parkpe_brand()
    service = VoucherService()
    out = service.issue_single_voucher(
        brand_id=brand.id,
        amount=Decimal("100.00"),
        issued_by=issuer,
        issuer_type="ADMIN",
        metadata={"source": "test_claim"},
    )
    pin = out["pin"]

    api_client.force_authenticate(user=owner2)
    with patch("api.parkpe_api.views.get_parkpe_brand_id", return_value=brand.id):
        response = api_client.post(
            "/api/voucher/vouchers/claim",
            {"voucherCode": out["voucher_code"], "pin": pin},
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["success"] is True
    assert "voucherId" in body

    from portal.models import GiftVoucher

    v = GiftVoucher.objects.get(id=body["voucherId"])
    assert (v.metadata or {}).get("parkpe_user_id") == owner2.pk


@pytest.mark.django_db
def test_claim_wrong_pin(api_client):
    issuer = _customer()
    brand = _parkpe_brand()
    service = VoucherService()
    out = service.issue_single_voucher(
        brand_id=brand.id,
        amount=Decimal("50.00"),
        issued_by=issuer,
        issuer_type="ADMIN",
    )
    user = _other_customer()
    api_client.force_authenticate(user=user)
    with patch("api.parkpe_api.views.get_parkpe_brand_id", return_value=brand.id):
        response = api_client.post(
            "/api/voucher/vouchers/claim",
            {"voucherCode": out["voucher_code"], "pin": "9999"},
            format="json",
        )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_claim_forbidden_when_linked_to_other_user(api_client):
    issuer = _customer()
    brand = _parkpe_brand()
    service = VoucherService()
    out = service.issue_single_voucher(
        brand_id=brand.id,
        amount=Decimal("50.00"),
        issued_by=issuer,
        issuer_type="ADMIN",
    )
    from portal.models import GiftVoucher

    v = GiftVoucher.objects.get(voucher_code=out["voucher_code"].replace("-", ""))
    other = _other_customer()
    meta = dict(v.metadata or {})
    meta["parkpe_user_id"] = other.pk
    v.metadata = meta
    v.save(update_fields=["metadata"])

    user = _customer(phone="+919000000001")
    api_client.force_authenticate(user=user)
    with patch("api.parkpe_api.views.get_parkpe_brand_id", return_value=brand.id):
        response = api_client.post(
            "/api/voucher/vouchers/claim",
            {"voucherCode": out["voucher_code"], "pin": out["pin"]},
            format="json",
        )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_claim_idempotent_same_user(api_client):
    issuer = _customer()
    brand = _parkpe_brand()
    service = VoucherService()
    out = service.issue_single_voucher(
        brand_id=brand.id,
        amount=Decimal("25.00"),
        issued_by=issuer,
        issuer_type="ADMIN",
    )
    user = _customer(phone="+919000000002")
    api_client.force_authenticate(user=user)
    with patch("api.parkpe_api.views.get_parkpe_brand_id", return_value=brand.id):
        r1 = api_client.post(
            "/api/voucher/vouchers/claim",
            {"voucherCode": out["voucher_code"], "pin": out["pin"]},
            format="json",
        )
        r2 = api_client.post(
            "/api/voucher/vouchers/claim",
            {"voucherCode": out["voucher_code"], "pin": out["pin"]},
            format="json",
        )
    assert r1.status_code == status.HTTP_200_OK
    assert r2.status_code == status.HTTP_200_OK
    assert r2.json().get("message")


@pytest.mark.django_db
def test_resolve_parkpe_user_id_from_mobile_matches_profile():
    role, _ = Role.objects.get_or_create(
        code="customer",
        defaults={"name": "Customer", "category": "b2c", "hierarchy_level": 1},
    )
    u = User.objects.create_user(
        username=_unique_username("bp"),
        password="z",
        role_code="customer",
        role=role,
        is_active=True,
    )
    Profile.objects.create(
        user=u,
        first_name="Bulk",
        last_name="Mobile",
        email="bulk.mobile@example.com",
        phone="+919811122233",
    )
    uid = _resolve_parkpe_user_id_from_mobile("9811122233")
    assert uid == u.pk


@pytest.mark.django_db
def test_resolve_parkpe_user_id_from_mobile_returns_none_if_no_match():
    assert _resolve_parkpe_user_id_from_mobile("9876500000") is None
