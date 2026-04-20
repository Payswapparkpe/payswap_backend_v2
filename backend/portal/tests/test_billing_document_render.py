"""Receipt HTML helpers — legacy exempt display."""
from decimal import Decimal
from types import SimpleNamespace

from portal.services.billing_document_render import _receipt_primary_supply_row


def test_primary_supply_row_legacy_exempt_uses_grand_total():
    doc = SimpleNamespace(
        taxable_amount=Decimal("0"),
        grand_total=Decimal("50.00"),
        gst_total=Decimal("0"),
        snapshot={
            "is_gst_exempt": True,
            "gst_rate_applied": "0",
            "is_pass_through": False,
        },
    )
    label, amt = _receipt_primary_supply_row(doc)
    assert "Value of supply" in label
    assert amt == "50.00"


def test_primary_supply_row_pass_through_keeps_stored_taxable():
    doc = SimpleNamespace(
        taxable_amount=Decimal("0"),
        grand_total=Decimal("500.00"),
        gst_total=Decimal("0"),
        snapshot={"is_pass_through": True, "is_gst_exempt": True, "gst_rate_applied": "0"},
    )
    label, amt = _receipt_primary_supply_row(doc)
    assert "pass-through" in label.lower()
    assert amt in ("0", "0.00")


def test_primary_supply_row_with_gst_uses_taxable():
    doc = SimpleNamespace(
        taxable_amount=Decimal("100.00"),
        grand_total=Decimal("118.00"),
        gst_total=Decimal("18.00"),
        snapshot={"gst_rate_applied": "18"},
    )
    label, amt = _receipt_primary_supply_row(doc)
    assert label == "Taxable amount"
    assert amt == "100.00"
