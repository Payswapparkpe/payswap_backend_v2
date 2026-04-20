"""
GST/TDS snapshot computation from TaxServiceProfile (service-wise config).
Phase 1: intra-state split of combined GST into CGST/SGST; IGST reserved at 0.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.utils import timezone

from portal.models import TaxServiceProfile

Q2 = Decimal("0.01")


def _quantize_money(d: Decimal) -> Decimal:
    return d.quantize(Q2, rounding=ROUND_HALF_UP)


def get_active_tax_profile(
    *,
    service_code: str,
    document_subtype: str = TaxServiceProfile.DOC_B2C,
    as_of=None,
) -> TaxServiceProfile | None:
    code = (service_code or "other").strip().lower() or "other"
    allowed = {TaxServiceProfile.DOC_B2C, TaxServiceProfile.DOC_B2B}
    sub = document_subtype if document_subtype in allowed else TaxServiceProfile.DOC_B2C
    ref = as_of or timezone.now()
    day = ref.date() if hasattr(ref, "date") else ref
    return (
        TaxServiceProfile.objects.filter(
            service_code=code,
            document_subtype=sub,
            is_active=True,
            effective_from__lte=day,
        )
        .order_by("-effective_from", "-pk")
        .first()
    )


def compute_tax_snapshot(
    *,
    service_code: str,
    document_subtype: str,
    amount: Decimal,
    document_type: str,
) -> dict[str, Any]:
    """
    Compute frozen tax fields for a BillingDocument.
    - B2C (document_subtype b2c_receipt): `amount` is customer total (default tax-inclusive).
    - B2B commission: `amount` is exclusive commission base; GST added; TDS on base per profile.
    """
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    code = (service_code or "other").strip().lower() or "other"
    profile = get_active_tax_profile(service_code=code, document_subtype=document_subtype)

    base_meta: dict[str, Any] = {
        "service_code": code,
        "document_subtype": document_subtype,
        "document_type": document_type,
        "sac_or_hsn": (getattr(profile, "sac_or_hsn", None) or "") if profile else "",
    }

    if profile is None:
        return {
            "taxable_amount": Decimal("0"),
            "cgst_amount": Decimal("0"),
            "sgst_amount": Decimal("0"),
            "igst_amount": Decimal("0"),
            "gst_total": Decimal("0"),
            "tds_amount": Decimal("0"),
            "grand_total": _quantize_money(amount),
            "snapshot": {**base_meta, "supply_type": "intra_state", "note": "No tax profile"},
        }

    gst_rate = profile.gst_rate or Decimal("0")
    tds_rate = profile.tds_rate or Decimal("0")

    igst = Decimal("0")

    if document_subtype == TaxServiceProfile.DOC_B2B:
        taxable = _quantize_money(amount)
        if profile.is_gst_exempt or gst_rate <= 0:
            gst_total = Decimal("0")
        else:
            gst_total = _quantize_money(taxable * gst_rate / Decimal("100"))
        cgst = _quantize_money(gst_total / 2)
        sgst = gst_total - cgst
        tds_amount = _quantize_money(taxable * tds_rate / Decimal("100")) if tds_rate > 0 else Decimal("0")
        grand_total = _quantize_money(taxable + gst_total)
    elif profile.is_pass_through:
        # Platform does not take a separate taxable base for GST (e.g. BBPS pass-through).
        taxable = Decimal("0")
        gst_total = Decimal("0")
        cgst = sgst = Decimal("0")
        grand_total = _quantize_money(amount)
        tds_amount = Decimal("0")
    elif profile.is_gst_exempt or gst_rate <= 0:
        # Exempt / nil-rated / 0%: full consideration is value of supply; GST lines remain zero.
        grand_total = _quantize_money(amount)
        taxable = grand_total
        gst_total = Decimal("0")
        cgst = sgst = Decimal("0")
        tds_amount = Decimal("0")
    elif profile.gst_inclusive:
        grand_total = _quantize_money(amount)
        r = gst_rate / Decimal("100")
        taxable = _quantize_money(grand_total / (Decimal("1") + r))
        gst_total = _quantize_money(grand_total - taxable)
        cgst = _quantize_money(gst_total / 2)
        sgst = gst_total - cgst
        tds_amount = Decimal("0")
    else:
        taxable = _quantize_money(amount)
        gst_total = _quantize_money(taxable * gst_rate / Decimal("100"))
        cgst = _quantize_money(gst_total / 2)
        sgst = gst_total - cgst
        grand_total = _quantize_money(taxable + gst_total)
        tds_amount = Decimal("0")

    snap = {
        **base_meta,
        "gst_rate_applied": str(gst_rate),
        "tds_rate_applied": str(tds_rate) if tds_rate else None,
        "gst_inclusive": profile.gst_inclusive,
        "is_pass_through": profile.is_pass_through,
        "is_gst_exempt": profile.is_gst_exempt,
        "supply_type": "intra_state",
        "lines": [
            {
                "description": f"Service: {code}",
                "taxable": str(taxable),
                "cgst": str(cgst),
                "sgst": str(sgst),
                "igst": str(igst),
            }
        ],
    }

    return {
        "taxable_amount": taxable,
        "cgst_amount": cgst,
        "sgst_amount": sgst,
        "igst_amount": igst,
        "gst_total": gst_total,
        "tds_amount": tds_amount,
        "grand_total": grand_total,
        "snapshot": snap,
    }
