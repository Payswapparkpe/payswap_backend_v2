"""
Billing / invoice party (buyer) snapshot from Profile or ResellerPartner.
Used when issuing BillingDocument so address & state are frozen on the document.
"""
from __future__ import annotations

from typing import Any

from django.conf import settings

from portal.models import Profile, ResellerPartner


def profile_billing_address_complete(profile: Profile | None) -> bool:
    """Minimum fields for GST-style place-of-supply on B2C receipts (CA may tighten)."""
    if not profile:
        return False
    line1 = (profile.address_line_1 or "").strip()
    st = (profile.state or "").strip()
    pc = (profile.pincode or "").strip()
    if not line1 or not st:
        return False
    if len(pc) < 6 or not pc.isdigit():
        return False
    return True


def party_dict_from_profile(profile: Profile | None) -> dict[str, Any]:
    if not profile:
        return {
            "type": "b2c_consumer",
            "billing_address_complete": False,
            "name": "",
            "email": "",
            "phone": "",
            "address_line_1": "",
            "address_line_2": "",
            "city": "",
            "state": "",
            "pincode": "",
            "country": "India",
            "gstin": "",
        }
    gstin = (getattr(profile, "gst_number", None) or "").strip()
    return {
        "type": "b2c_consumer",
        "billing_address_complete": profile_billing_address_complete(profile),
        "name": (profile.full_name or "").strip(),
        "email": (profile.email or "").strip(),
        "phone": (profile.phone or "").strip(),
        "address_line_1": (profile.address_line_1 or "").strip(),
        "address_line_2": (profile.address_line_2 or "").strip(),
        "city": (profile.city or "").strip(),
        "state": (profile.state or "").strip(),
        "pincode": (profile.pincode or "").strip(),
        "country": (profile.country_of_residence or "India").strip(),
        "gstin": gstin,
    }


def party_dict_from_partner(partner: ResellerPartner | None) -> dict[str, Any]:
    if not partner:
        return {"type": "b2b_partner", "billing_address_complete": False, "name": ""}
    addr = (partner.address or "").strip()
    return {
        "type": "b2b_partner",
        "billing_address_complete": bool(addr and (partner.gst_number or "").strip()),
        "name": (partner.company_name or "").strip(),
        "email": (partner.email or "").strip(),
        "phone": (partner.phone or "").strip(),
        "address_line_1": addr,
        "address_line_2": "",
        "city": "",
        "state": "",
        "pincode": "",
        "country": "India",
        "gstin": (partner.gst_number or "").strip(),
    }


def party_snapshot_for_billing(*, user, partner) -> dict[str, Any]:
    if user and getattr(user, "pk", None):
        prof = getattr(user, "profile", None)
        if prof is None:
            prof = Profile.objects.filter(user=user).first()
        return party_dict_from_profile(prof)
    if partner:
        return party_dict_from_partner(partner)
    return party_dict_from_profile(None)


def parkpe_billing_address_required() -> bool:
    return bool(getattr(settings, "PARKPE_REQUIRE_BILLING_ADDRESS", False))


def billing_address_error_payload() -> dict[str, Any]:
    return {
        "detail": "Add your billing address (PIN code, state, and address line) under Settings before paying.",
        "code": "billing_address_incomplete",
        "billingAddressComplete": False,
    }
