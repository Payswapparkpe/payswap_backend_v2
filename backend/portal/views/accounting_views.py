"""Hub portal: Accounting — billing documents, tax profiles, exports."""
from __future__ import annotations

import csv
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView

from portal.models import BillingDocument, TaxServiceProfile
from portal.services.billing_document_render import (
    billing_document_display_label,
    html_to_pdf_bytes,
    render_billing_document_html,
    safe_download_filename,
)
from portal.views.parkpe_hub_views import _is_parkpe_admin


def _require_admin(request):
    if not _is_parkpe_admin(request.user):
        messages.error(request, "Access denied. Admin role required.")
        return redirect("/dashboard/")
    return None


def filtered_billing_document_queryset(request):
    """Shared filters for Accounting documents list, CSV export, and reports."""
    qs = BillingDocument.objects.select_related("user", "partner").all()
    sc = (request.GET.get("service_code") or "").strip().lower()
    if sc:
        qs = qs.filter(service_code=sc)
    dt = (request.GET.get("document_type") or "").strip()
    if dt:
        qs = qs.filter(document_type=dt)
    df = (request.GET.get("date_from") or "").strip()
    dt_to = (request.GET.get("date_to") or "").strip()
    if df:
        qs = qs.filter(issued_at__date__gte=df)
    if dt_to:
        qs = qs.filter(issued_at__date__lte=dt_to)
    return qs


def _billing_export_querystring(request, extra: dict | None = None) -> str:
    from urllib.parse import urlencode

    keep = {}
    for k in ("service_code", "document_type", "date_from", "date_to"):
        v = (request.GET.get(k) or "").strip()
        if v:
            keep[k] = v
    if extra:
        keep.update(extra)
    return urlencode(keep)


@method_decorator(login_required, name="dispatch")
class AccountingDashboardView(TemplateView):
    template_name = "portal/accounting/dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        r = _require_admin(request)
        if r:
            return r
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        since = timezone.now() - timedelta(days=30)
        qs = BillingDocument.objects.filter(issued_at__gte=since)
        ctx["period_days"] = 30
        ctx["document_count"] = qs.count()
        ctx["gst_total"] = qs.aggregate(s=Sum("gst_total"))["s"] or Decimal("0")
        ctx["tds_total"] = qs.aggregate(s=Sum("tds_amount"))["s"] or Decimal("0")
        ctx["taxable_total"] = qs.aggregate(s=Sum("taxable_amount"))["s"] or Decimal("0")
        ctx["grand_total_sum"] = qs.aggregate(s=Sum("grand_total"))["s"] or Decimal("0")
        ctx["active_tax_profiles"] = TaxServiceProfile.objects.filter(is_active=True).count()
        ctx["by_service"] = list(
            qs.values("service_code")
            .annotate(n=Count("id"), gst=Sum("gst_total"), doc_total=Sum("grand_total"))
            .order_by("-n")[:12]
        )
        return ctx


@method_decorator(login_required, name="dispatch")
class AccountingReportsView(TemplateView):
    """
    Cumulative billing / tax summaries and CSV exports (aggregates + sample rows).
    """

    template_name = "portal/accounting/reports.html"

    def dispatch(self, request, *args, **kwargs):
        r = _require_admin(request)
        if r:
            return r
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        exp = (request.GET.get("export") or "").strip().lower()
        if exp == "services":
            return self._export_services_csv(request)
        if exp in ("document_types", "doctypes"):
            return self._export_document_types_csv(request)
        return super().get(request, *args, **kwargs)

    def _export_services_csv(self, request):
        qs = filtered_billing_document_queryset(request)
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="billing_aggregate_by_service.csv"'
        w = csv.writer(resp)
        w.writerow(
            [
                "service_code",
                "document_count",
                "sum_grand_total",
                "sum_taxable",
                "sum_gst_total",
                "sum_tds",
            ]
        )
        for row in (
            qs.values("service_code")
            .annotate(
                n=Count("id"),
                g=Sum("grand_total"),
                tx=Sum("taxable_amount"),
                gst=Sum("gst_total"),
                tds=Sum("tds_amount"),
            )
            .order_by("service_code")
        ):
            w.writerow(
                [
                    row["service_code"],
                    row["n"],
                    row["g"],
                    row["tx"],
                    row["gst"],
                    row["tds"],
                ]
            )
        return resp

    def _export_document_types_csv(self, request):
        qs = filtered_billing_document_queryset(request)
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="billing_aggregate_by_document_type.csv"'
        w = csv.writer(resp)
        w.writerow(
            [
                "document_type",
                "document_count",
                "sum_grand_total",
                "sum_taxable",
                "sum_gst_total",
                "sum_tds",
            ]
        )
        for row in (
            qs.values("document_type")
            .annotate(
                n=Count("id"),
                g=Sum("grand_total"),
                tx=Sum("taxable_amount"),
                gst=Sum("gst_total"),
                tds=Sum("tds_amount"),
            )
            .order_by("document_type")
        ):
            w.writerow(
                [
                    row["document_type"],
                    row["n"],
                    row["g"],
                    row["tx"],
                    row["gst"],
                    row["tds"],
                ]
            )
        return resp

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        request = self.request
        qs = filtered_billing_document_queryset(request)
        ctx["filters"] = {
            "service_code": request.GET.get("service_code") or "",
            "document_type": request.GET.get("document_type") or "",
            "date_from": request.GET.get("date_from") or "",
            "date_to": request.GET.get("date_to") or "",
        }
        ctx["total_docs"] = qs.count()
        ctx["sum_grand"] = qs.aggregate(s=Sum("grand_total"))["s"] or Decimal("0")
        ctx["sum_taxable"] = qs.aggregate(s=Sum("taxable_amount"))["s"] or Decimal("0")
        ctx["sum_gst"] = qs.aggregate(s=Sum("gst_total"))["s"] or Decimal("0")
        ctx["sum_tds"] = qs.aggregate(s=Sum("tds_amount"))["s"] or Decimal("0")
        ctx["by_service"] = list(
            qs.values("service_code")
            .annotate(
                n=Count("id"),
                g=Sum("grand_total"),
                gst=Sum("gst_total"),
                tx=Sum("taxable_amount"),
            )
            .order_by("-n")[:30]
        )
        ctx["by_doctype"] = list(
            qs.values("document_type")
            .annotate(n=Count("id"), g=Sum("grand_total"), gst=Sum("gst_total"))
            .order_by("document_type")
        )
        ctx["by_doctype_labeled"] = [
            {
                "document_type": r["document_type"],
                "label": billing_document_display_label(r["document_type"]),
                "n": r["n"],
                "g": r["g"],
                "gst": r["gst"],
            }
            for r in ctx["by_doctype"]
        ]
        ctx["recent_docs"] = list(qs.order_by("-issued_at")[:40])
        base = reverse("accounting_documents")
        q = _billing_export_querystring(request)
        ctx["documents_filtered_url"] = f"{base}?{q}" if q else base
        ctx["documents_csv_url"] = f"{base}?{_billing_export_querystring(request, {'export': 'csv'})}"
        rep = reverse("accounting_reports")
        ctx["export_services_csv_url"] = f"{rep}?{_billing_export_querystring(request, {'export': 'services'})}"
        ctx["export_doctypes_csv_url"] = f"{rep}?{_billing_export_querystring(request, {'export': 'document_types'})}"
        return ctx


@method_decorator(login_required, name="dispatch")
class AccountingDocumentsView(TemplateView):
    template_name = "portal/accounting/documents.html"

    def dispatch(self, request, *args, **kwargs):
        r = _require_admin(request)
        if r:
            return r
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") == "csv":
            return self._export_csv(request)
        return super().get(request, *args, **kwargs)

    def _export_csv(self, request):
        qs = filtered_billing_document_queryset(request)
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="billing_documents.csv"'
        w = csv.writer(resp)
        w.writerow(
            [
                "id",
                "issued_at",
                "document_type",
                "service_code",
                "reference_id",
                "user_id",
                "partner_id",
                "party_name",
                "party_state",
                "party_pincode",
                "taxable",
                "cgst",
                "sgst",
                "gst_total",
                "tds",
                "grand_total",
            ]
        )
        for d in qs.order_by("-issued_at")[:5000]:
            snap = d.snapshot if isinstance(d.snapshot, dict) else {}
            party = snap.get("party") if isinstance(snap.get("party"), dict) else {}
            party_name = (party.get("name") or "").strip()
            party_state = (party.get("state") or "").strip()
            party_pincode = (party.get("pincode") or "").strip()
            w.writerow(
                [
                    d.pk,
                    d.issued_at.isoformat(),
                    d.document_type,
                    d.service_code,
                    d.reference_id,
                    d.user_id or "",
                    d.partner_id or "",
                    party_name,
                    party_state,
                    party_pincode,
                    d.taxable_amount,
                    d.cgst_amount,
                    d.sgst_amount,
                    d.gst_total,
                    d.tds_amount,
                    d.grand_total,
                ]
            )
        return resp

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        request = self.request
        qs = filtered_billing_document_queryset(request)
        ctx["documents"] = list(qs.order_by("-issued_at")[:500])
        ctx["filters"] = {
            "service_code": request.GET.get("service_code") or "",
            "document_type": request.GET.get("document_type") or "",
            "date_from": request.GET.get("date_from") or "",
            "date_to": request.GET.get("date_to") or "",
        }
        ctx["documents_csv_url"] = (
            f"{reverse('accounting_documents')}?{_billing_export_querystring(request, {'export': 'csv'})}"
        )
        ctx["accounting_reports_url"] = (
            f"{reverse('accounting_reports')}?{_billing_export_querystring(request)}"
            if _billing_export_querystring(request)
            else reverse("accounting_reports")
        )
        return ctx


@method_decorator(login_required, name="dispatch")
class AccountingTaxProfilesView(View):
    """List tax profiles + create via POST."""

    def dispatch(self, request, *args, **kwargs):
        r = _require_admin(request)
        if r:
            return r
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        profiles = TaxServiceProfile.objects.order_by("service_code", "document_subtype")
        return render(request, "portal/accounting/tax_profiles.html", {"profiles": profiles})

    def post(self, request):
        action = (request.POST.get("action") or "").strip().lower()
        if action == "delete":
            pk = request.POST.get("pk")
            try:
                obj = TaxServiceProfile.objects.get(pk=int(pk))
            except (TypeError, ValueError, TaxServiceProfile.DoesNotExist):
                messages.error(request, "Invalid profile.")
                return redirect("accounting_tax_profiles")
            obj.delete()
            messages.success(request, "Tax profile deleted.")
            return redirect("accounting_tax_profiles")
        # create
        try:
            ef_raw = (request.POST.get("effective_from") or "").strip()
            try:
                eff = date.fromisoformat(ef_raw) if ef_raw else timezone.now().date()
            except ValueError:
                eff = timezone.now().date()
            TaxServiceProfile.objects.create(
                service_code=(request.POST.get("service_code") or "").strip().lower()[:50],
                document_subtype=(request.POST.get("document_subtype") or TaxServiceProfile.DOC_B2C).strip(),
                sac_or_hsn=(request.POST.get("sac_or_hsn") or "")[:32],
                gst_rate=Decimal(str(request.POST.get("gst_rate") or "0")),
                gst_inclusive=request.POST.get("gst_inclusive") == "on",
                is_gst_exempt=request.POST.get("is_gst_exempt") == "on",
                is_pass_through=request.POST.get("is_pass_through") == "on",
                tds_rate=(
                    Decimal(str(request.POST.get("tds_rate")))
                    if (request.POST.get("tds_rate") or "").strip()
                    else None
                ),
                effective_from=eff,
                is_active=request.POST.get("is_active") == "on",
                notes=(request.POST.get("notes") or "")[:2000],
            )
            messages.success(request, "Tax profile created.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("accounting_tax_profiles")


@method_decorator(login_required, name="dispatch")
class AccountingTaxProfileEditView(View):
    def dispatch(self, request, *args, **kwargs):
        r = _require_admin(request)
        if r:
            return r
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk: int):
        profile = get_object_or_404(TaxServiceProfile, pk=pk)
        return render(request, "portal/accounting/tax_profile_edit.html", {"profile": profile})

    def post(self, request, pk: int):
        profile = get_object_or_404(TaxServiceProfile, pk=pk)
        profile.service_code = (request.POST.get("service_code") or profile.service_code).strip().lower()[:50]
        profile.document_subtype = (request.POST.get("document_subtype") or profile.document_subtype).strip()
        profile.sac_or_hsn = (request.POST.get("sac_or_hsn") or "")[:32]
        profile.gst_rate = Decimal(str(request.POST.get("gst_rate") or "0"))
        profile.gst_inclusive = request.POST.get("gst_inclusive") == "on"
        profile.is_gst_exempt = request.POST.get("is_gst_exempt") == "on"
        profile.is_pass_through = request.POST.get("is_pass_through") == "on"
        tr = (request.POST.get("tds_rate") or "").strip()
        profile.tds_rate = Decimal(str(tr)) if tr else None
        ef_raw = (request.POST.get("effective_from") or "").strip()
        if ef_raw:
            try:
                profile.effective_from = date.fromisoformat(ef_raw)
            except ValueError:
                pass
        profile.is_active = request.POST.get("is_active") == "on"
        profile.notes = (request.POST.get("notes") or "")[:2000]
        try:
            profile.save()
            messages.success(request, "Tax profile updated.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect("accounting_tax_profiles")


@method_decorator(login_required, name="dispatch")
class AccountingBillingDocumentHtmlView(View):
    """Staff HTML view of a billing document (for print / audit)."""

    def dispatch(self, request, *args, **kwargs):
        r = _require_admin(request)
        if r:
            return r
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk: int):
        doc = get_object_or_404(
            BillingDocument.objects.select_related("user", "partner"),
            pk=pk,
        )
        html = render_billing_document_html(
            doc,
            heading=f"{billing_document_display_label(doc.document_type)} · #{doc.pk}",
        )
        return HttpResponse(html, content_type="text/html; charset=utf-8")


@method_decorator(login_required, name="dispatch")
class AccountingBillingDocumentDownloadView(View):
    """Download billing document as HTML file or PDF (PDF requires xhtml2pdf)."""

    def dispatch(self, request, *args, **kwargs):
        r = _require_admin(request)
        if r:
            return r
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk: int):
        doc = get_object_or_404(
            BillingDocument.objects.select_related("user", "partner"),
            pk=pk,
        )
        fmt = (request.GET.get("format") or "html").strip().lower()
        html = render_billing_document_html(
            doc,
            heading=f"{billing_document_display_label(doc.document_type)} · #{doc.pk}",
        )
        if fmt == "pdf":
            pdf = html_to_pdf_bytes(html)
            if not pdf:
                messages.warning(
                    request,
                    "PDF engine not available. Download HTML and use Print → Save as PDF in your browser.",
                )
                return redirect("accounting_billing_document_html", pk=pk)
            resp = HttpResponse(pdf, content_type="application/pdf")
            resp["Content-Disposition"] = (
                f'attachment; filename="{safe_download_filename(doc, "pdf")}"'
            )
            return resp
        resp = HttpResponse(html, content_type="text/html; charset=utf-8")
        resp["Content-Disposition"] = (
            f'attachment; filename="{safe_download_filename(doc, "html")}"'
        )
        return resp
