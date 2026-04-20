"""HTML (and optional PDF) rendering for BillingDocument — shared by Hub Accounting and ParkPe API."""
from __future__ import annotations

import json
import re

from django.utils.html import escape

from portal.models import BillingDocument, Profile


def _place_of_supply_state(doc: BillingDocument) -> str:
    snap = doc.snapshot or {}
    party = snap.get("party") if isinstance(snap.get("party"), dict) else {}
    st = (party.get("state") or "").strip()
    if st:
        return st
    if doc.user_id:
        u = getattr(doc, "user", None)
        if u is not None:
            try:
                prof = Profile.objects.filter(user=u).only("state").first()
                if prof and (prof.state or "").strip():
                    return (prof.state or "").strip()
            except Exception:
                pass
    return ""


def _party_section_html(doc: BillingDocument) -> str:
    """Prefer frozen snapshot['party']; fall back to live Profile for older documents."""
    snap = doc.snapshot or {}
    party = snap.get("party") if isinstance(snap.get("party"), dict) else {}
    lines: list[str] = []

    if party and (party.get("name") or party.get("address_line_1") or party.get("gstin")):
        bits: list[str] = []
        pname = (party.get("name") or "").strip()
        if pname:
            bits.append(f"<strong>Name:</strong> {escape(pname)}")
        em = (party.get("email") or "").strip()
        if em:
            bits.append(f"<strong>Email:</strong> {escape(em)}")
        ph = (party.get("phone") or "").strip()
        if ph:
            bits.append(f"<strong>Mobile:</strong> {escape(ph)}")
        gst = (party.get("gstin") or "").strip()
        if gst:
            bits.append(f"<strong>GSTIN:</strong> {escape(gst)}")
        addr_parts: list[str] = []
        a1 = (party.get("address_line_1") or "").strip()
        a2 = (party.get("address_line_2") or "").strip()
        city = (party.get("city") or "").strip()
        st = (party.get("state") or "").strip()
        pc = (party.get("pincode") or "").strip()
        ctry = (party.get("country") or "").strip()
        if a1:
            addr_parts.append(escape(a1))
        if a2:
            addr_parts.append(escape(a2))
        locality = ", ".join(x for x in [city, st, pc] if x)
        if locality:
            addr_parts.append(escape(locality))
        if ctry:
            addr_parts.append(escape(ctry))
        if addr_parts:
            bits.append("<strong>Address:</strong> " + " · ".join(addr_parts))
        if bits:
            lines.append("<p><strong>Bill to</strong> · " + " &nbsp;·&nbsp; ".join(bits) + "</p>")
    elif doc.user_id:
        u = getattr(doc, "user", None)
        if u is not None:
            payer_name = ""
            payer_email = ""
            payer_phone = ""
            try:
                prof = (
                    Profile.objects.filter(user=u)
                    .only("first_name", "middle_name", "last_name", "email", "phone")
                    .first()
                )
                if prof:
                    payer_name = str(prof.full_name or "").strip()
                    payer_email = str(prof.email or "").strip()
                    payer_phone = str(prof.phone or "").strip()
            except Exception:
                pass
            if not payer_name:
                payer_name = str(getattr(u, "username", None) or getattr(u, "email", None) or u.pk)
            bits2 = [f"<strong>Name:</strong> {escape(payer_name)}"]
            if payer_email:
                bits2.append(f"<strong>Email:</strong> {escape(payer_email)}")
            if payer_phone:
                bits2.append(f"<strong>Mobile:</strong> {escape(payer_phone)}")
            lines.append("<p><strong>Bill to</strong> · " + " &nbsp;·&nbsp; ".join(bits2) + "</p>")
    if doc.partner_id and (party.get("type") or "") != "b2b_partner":
        p = getattr(doc, "partner", None)
        pname = ""
        if p is not None:
            pname = getattr(p, "company_name", None) or getattr(p, "partner_code", None) or str(p.pk)
        lines.append(f"<p><strong>Partner:</strong> {escape(str(pname))} (id {doc.partner_id})</p>")
    return "".join(lines)


def _receipt_primary_supply_row(doc: BillingDocument) -> tuple[str, str]:
    """
    First summary row label + amount for print/HTML.

    Legacy exempt documents may have taxable_amount=0 in DB while grand_total is correct;
    show value of supply as grand_total so the receipt does not read as '₹0 taxable, ₹50 total'.
    """
    snap = doc.snapshot or {}

    def _f(x) -> float:
        try:
            return float(x or 0)
        except (TypeError, ValueError):
            return 0.0

    ta = _f(doc.taxable_amount)
    gt = _f(doc.grand_total)
    gst = _f(doc.gst_total)

    if gst != 0:
        return "Taxable amount", str(doc.taxable_amount)
    if snap.get("is_pass_through"):
        return "Taxable amount (pass-through)", str(doc.taxable_amount)
    if ta > 0:
        return "Taxable amount", str(doc.taxable_amount)
    if gt > 0 and (
        snap.get("is_gst_exempt")
        or str(snap.get("gst_rate_applied") or "") in ("0", "0.0", "0.00")
        or snap.get("note") == "No tax profile"
    ):
        return "Value of supply (GST nil / exempt)", str(doc.grand_total)
    return "Taxable amount", str(doc.taxable_amount)


def _gst_transparency_note_html(doc: BillingDocument) -> str:
    """
    Clarify receipts where GST is nil: frozen rows may show taxable 0 with positive grand total
    (older exempt logic) or full value-of-supply with nil GST (current engine).
    """
    snap = doc.snapshot or {}
    try:
        gt = float(doc.grand_total or 0)
        ta = float(doc.taxable_amount or 0)
        gtot = float(doc.gst_total or 0)
    except (TypeError, ValueError):
        return ""
    if gt <= 0:
        return ""
    if gtot > 0:
        return ""
    if snap.get("is_pass_through"):
        return (
            '<p class="gst-note" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;'
            'padding:12px 14px;font-size:14px;line-height:1.45">'
            "<strong>Note:</strong> This supply is configured as <strong>pass-through</strong> for GST "
            "(no tax collected on this leg). The <strong>Grand total</strong> is the amount received."
            "</p>"
        )
    if snap.get("note") == "No tax profile":
        return (
            '<p class="gst-note" style="background:#fffbeb;border:1px solid #fcd34d;border-radius:8px;'
            'padding:12px 14px;font-size:14px;line-height:1.45">'
            "<strong>Note:</strong> No active tax profile was configured for this service at issue time. "
            "GST is shown as nil; the <strong>Grand total</strong> is the consideration recorded."
            "</p>"
        )
    if snap.get("is_gst_exempt") or str(snap.get("gst_rate_applied") or "") in ("0", "0.0", "0.00"):
        if ta <= 0 and gt > 0 and not snap.get("is_pass_through"):
            return (
                '<p class="gst-note" style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;'
                'padding:12px 14px;font-size:14px;line-height:1.45">'
                "<strong>GST break-up:</strong> Nil (exempt / zero-rated under the active tax profile). "
                "The first row in the table is the <strong>value of supply</strong> (consideration received). "
                "CGST/SGST/IGST are ₹0.00."
                "</p>"
            )
        return (
            '<p class="gst-note" style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;'
            'padding:12px 14px;font-size:14px;line-height:1.45">'
            "<strong>GST break-up:</strong> Nil (exempt / zero-rated). "
            "The first row is the taxable value of supply; CGST/SGST are ₹0.00."
            "</p>"
        )
    return ""


def billing_document_display_label(document_type: str) -> str:
    dt = (document_type or "").strip()
    if dt == BillingDocument.DOC_B2C_RECEIPT:
        return "Tax receipt"
    if dt == BillingDocument.DOC_CREDIT_NOTE:
        return "Credit note"
    if dt == BillingDocument.DOC_B2B_COMMISSION:
        return "Commission invoice"
    return dt or "Document"


def render_billing_document_html(
    doc: BillingDocument,
    *,
    heading: str | None = None,
    include_print_hint: bool = True,
) -> str:
    """Print-friendly HTML for a billing document (amounts are escaped; snapshot JSON is escaped)."""
    label = billing_document_display_label(doc.document_type)
    title = escape(heading or f"{label} · #{doc.pk}")
    ref = escape(str(doc.reference_id or ""))
    svc = escape(str(doc.service_code or ""))
    dtype = escape(str(doc.document_type or ""))
    issued = escape(doc.issued_at.isoformat() if doc.issued_at else "")
    party_lines = _party_section_html(doc)
    pos_state = _place_of_supply_state(doc)

    snap_raw = doc.snapshot or {}
    snap_json = json.dumps(snap_raw, indent=2, default=str)
    snap_safe = escape(snap_json)

    v_label, v_amount = _receipt_primary_supply_row(doc)
    supply_row = f"<tr><th>{escape(v_label)}</th><td class=\"amount\">{escape(v_amount)}</td></tr>"

    print_block = ""
    if include_print_hint:
        print_block = '<p class="no-print" style="color:#666;font-size:13px">Use your browser <strong>Print → Save as PDF</strong> if PDF download is not available.</p>'

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
  body{{font-family:system-ui,-apple-system,sans-serif;max-width:720px;margin:24px auto;padding:0 20px 40px;color:#111;line-height:1.45}}
  h1{{font-size:1.35rem;margin-bottom:0.25rem}}
  .sub{{color:#555;font-size:0.95rem;margin-top:0}}
  table{{width:100%;border-collapse:collapse;margin-top:16px}}
  th,td{{border:1px solid #ccc;padding:10px 8px;text-align:left;font-size:14px}}
  th{{background:#f4f4f5;width:38%}}
  .amount{{font-weight:600}}
  pre{{background:#f6f6f6;padding:12px;font-size:11px;overflow:auto;border:1px solid #e5e5e5;border-radius:6px;white-space:pre-wrap;word-break:break-word}}
  @media print{{.no-print{{display:none!important}}}}
</style></head><body>
<h1>{escape(label)}</h1>
<p class="sub">Document #{doc.pk} · {issued}</p>
{party_lines}
<p><strong>Reference:</strong> {ref}</p>
<p><strong>Service:</strong> {svc} &nbsp;·&nbsp; <strong>Internal type:</strong> {dtype}</p>
{_gst_transparency_note_html(doc)}
<table>
  <tr><th>Place of supply (State)</th><td>{escape(pos_state) if pos_state else "—"}</td></tr>
  {supply_row}
  <tr><th>CGST</th><td>{doc.cgst_amount}</td></tr>
  <tr><th>SGST</th><td>{doc.sgst_amount}</td></tr>
  <tr><th>IGST</th><td>{doc.igst_amount}</td></tr>
  <tr><th>GST total</th><td class="amount">{doc.gst_total}</td></tr>
  <tr><th>TDS</th><td>{doc.tds_amount}</td></tr>
  <tr><th>Grand total</th><td class="amount">{doc.grand_total} {escape(doc.currency or "INR")}</td></tr>
</table>
{print_block}
<h2 style="font-size:1rem;margin-top:28px">Snapshot (frozen at issue)</h2>
<pre>{snap_safe}</pre>
<p style="color:#666;font-size:12px;margin-top:24px">Amounts and tax lines are stored at issue time. Configuration changes do not alter issued documents.</p>
</body></html>"""


def html_to_pdf_bytes(html: str) -> bytes | None:
    """Return PDF bytes or None if xhtml2pdf is unavailable or conversion fails."""
    try:
        from portal.services.billing_service import _html_to_pdf

        return _html_to_pdf(html)
    except Exception:
        return None


def safe_download_filename(doc: BillingDocument, suffix: str) -> str:
    """ASCII-safe filename for Content-Disposition."""
    base = re.sub(r"[^a-zA-Z0-9._-]+", "_", f"billing_{doc.pk}_{doc.document_type}")[:120]
    return f"{base}.{suffix}"
