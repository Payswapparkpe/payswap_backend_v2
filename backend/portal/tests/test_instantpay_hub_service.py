import pytest

from decimal import Decimal
from django.contrib.auth import get_user_model

from portal.models import ApiVendor, InstantpayTransaction, Profile, ResellerPartner, Role, Wallet
from portal.services.instantpay_hub_service import InstantpayHubService

User = get_user_model()


def _create_partner():
    role, _ = Role.objects.get_or_create(
        code="admin",
        defaults={"name": "Admin", "category": "b2b", "hierarchy_level": 10},
    )
    user = User.objects.create_user(
        username=f"inst_{User.objects.count()+1}",
        password="testpass123",
        role_code="admin",
        role=role,
    )
    Profile.objects.get_or_create(
        user=user,
        defaults={"first_name": "Instant", "email": f"{user.username}@example.com", "phone": "919876543299"},
    )
    wallet, _ = Wallet.objects.get_or_create(
        user=user,
        defaults={"balance": Decimal("1000.00"), "currency": "INR", "status": "active"},
    )
    partner, _ = ResellerPartner.objects.get_or_create(
        partner_code=f"IPARTNER_{ResellerPartner.objects.count()+1}",
        defaults={
            "company_name": "Instantpay Test Partner",
            "contact_person": "Contact",
            "email": f"partner_{user.username}@example.com",
            "phone": "91999999998",
            "business_type": "PRIVATE_LTD",
            "address": "Address",
            "status": "ACTIVE",
            "onboarding_status": "APPROVED",
            "wallet": wallet,
        },
    )
    return partner


@pytest.mark.django_db
def test_execute_persists_instantpay_transaction(monkeypatch):
    partner = _create_partner()
    ApiVendor.objects.get_or_create(code="instantpay", defaults={"name": "Instantpay", "description": "Test vendor"})

    service = InstantpayHubService()
    monkeypatch.setattr(service.client, "is_configured", lambda: True)
    monkeypatch.setattr(
        service.client,
        "request",
        lambda api_code, payload, **kwargs: {
            "success": True,
            "status_code": 200,
            "json": {"reference_id": "IP-REF-1", "status": "SUCCESS"},
            "error": None,
        },
    )

    result = service.execute(
        "dmt_transfer",
        {
            "partner_txn_id": "PTX-INT-1",
            "beneficiary_account": "1234567890",
            "ifsc": "HDFC0001234",
            "amount": "1000",
        },
        partner_id=partner.id,
        partner_code=partner.partner_code,
        idempotency_key="idem-001",
    )

    assert result["success"] is True
    tx = InstantpayTransaction.objects.get(partner=partner, partner_txn_id="PTX-INT-1")
    assert tx.status == InstantpayTransaction.STATUS_SUCCESS
    assert tx.action == "dmt_transfer"
    assert tx.vendor_reference == "IP-REF-1"
    assert tx.idempotency_key == "idem-001"


@pytest.mark.django_db
def test_get_status_reads_transaction():
    partner = _create_partner()
    vendor, _ = ApiVendor.objects.get_or_create(code="instantpay", defaults={"name": "Instantpay", "description": "Test vendor"})
    InstantpayTransaction.objects.create(
        partner=partner,
        vendor=vendor,
        service_name="reconciliation",
        action="transaction_status",
        partner_txn_id="PTX-STAT-1",
        status=InstantpayTransaction.STATUS_PENDING,
        request_payload={"partner_txn_id": "PTX-STAT-1"},
        response_payload={"status": "PENDING"},
    )

    service = InstantpayHubService()
    result = service.get_status("PTX-STAT-1", partner_id=partner.id)

    assert result["success"] is True
    assert result["transaction"]["partner_txn_id"] == "PTX-STAT-1"
    assert result["transaction"]["status"] == InstantpayTransaction.STATUS_PENDING
