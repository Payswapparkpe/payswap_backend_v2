"""
/services/ – Integrated vendors and their services.
Shows which vendors are integrated and which services they power.
"""
from django.shortcuts import redirect
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.urls.resolvers import URLPattern, URLResolver
from datetime import timedelta
import json

from portal.models import ServiceFlowStep, ApiVendor, VendorApi, LogEntry
from portal.services.api_registry import (
    resolve_api_codes_for_view,
    infer_vendor_hints_for_view_module,
    runtime_token_hints_for_api,
)


SERVICE_NARRATION_BY_CODE = {
    "BBPS": "BBPS bill fetch and payment flows.",
    "AEPS": "Aadhaar-enabled cash withdrawal and balance enquiry.",
    "DMT": "Domestic money transfer flow for account payouts.",
    "FASTAG": "FASTag recharge and status checks.",
    "VERIFICATION_API": "Customer and account verification journeys.",
    "SMS_IVR_GATEWAY": "OTP, SMS alerts, and IVR-based communication.",
    "PAYMENT_GATEWAY": "Payment collection, auth, and settlement flow.",
}


def _is_services_admin(user):
    if not user or not user.is_authenticated:
        return False
    return getattr(user, "role_code", "").lower() in ("super_admin", "admin")


def _collect_v2_api_endpoint_usage():
    """
    Build api_code -> endpoint usage map by introspecting api/v2 URL patterns.
    """
    from collections import defaultdict
    from api.v2 import urls as api_v2_urls

    usage_map = defaultdict(list)

    def _walk(patterns, prefix=""):
        for p in patterns:
            if isinstance(p, URLResolver):
                _walk(p.url_patterns, prefix=f"{prefix}{p.pattern}")
                continue
            if not isinstance(p, URLPattern):
                continue

            callback = getattr(p, "callback", None)
            view_cls = getattr(callback, "view_class", None)
            if not view_cls:
                continue

            api_codes = resolve_api_codes_for_view(view_cls)
            if not api_codes:
                continue

            route = f"/api/v2/{prefix}{p.pattern}".replace("//", "/")
            module_name = getattr(view_cls, "__module__", "") or ""
            vendor_hints = infer_vendor_hints_for_view_module(module_name)
            for code in api_codes:
                usage_map[code].append(
                    {
                        "route": route,
                        "service_name": getattr(view_cls, "service_name", "") or "",
                        "view_name": view_cls.__name__,
                        "vendor_hints": vendor_hints,
                    }
                )

    _walk(api_v2_urls.urlpatterns)
    return dict(usage_map)


def _build_runtime_token_map(by_vendor, endpoint_usage_by_api):
    token_map = {}
    for vendor_code, vendor in by_vendor.items():
        for api in vendor.get("apis", []):
            key = (vendor_code, api["code"])
            tokens = set()
            api_code = api["code"].lower()
            if len(api_code) >= 4:
                tokens.add(api_code)
                tokens.add(api_code.replace("_", "-"))
                tokens.add(api_code.replace("_", " "))
            for link in endpoint_usage_by_api.get(api["code"], []):
                route_token = str(link.get("route") or "").replace("/api/v2/", "").strip("/").lower()
                if route_token:
                    tokens.add(route_token)
                    tokens.add(route_token.replace("/", " "))
            for hint in runtime_token_hints_for_api(api["code"]):
                hint_value = str(hint or "").strip().lower()
                if hint_value:
                    tokens.add(hint_value)
            token_map[key] = sorted(tokens, key=len, reverse=True)
    return token_map


def _match_runtime_metric_key(token_map, haystack):
    matched_key = None
    best_len = -1
    for key, tokens in token_map.items():
        for token in tokens:
            if token and token in haystack:
                if len(token) > best_len:
                    matched_key = key
                    best_len = len(token)
                break
    return matched_key


def _collect_api_runtime_metrics(by_vendor, endpoint_usage_by_api):
    """
    Build last-24h API metrics from LogEntry vendor logs.
    """
    since = timezone.now() - timedelta(days=1)
    entries = (
        LogEntry.objects
        .filter(timestamp__gte=since)
        .values("module_name", "log_level", "message", "url", "extra_data")
    )

    metrics = {}
    token_map = _build_runtime_token_map(by_vendor, endpoint_usage_by_api)
    for key in token_map:
        metrics[key] = {
            "hits": 0,
            "failures": 0,
            "successes": 0,
            "admin_blocked": 0,
            "response_total_ms": 0.0,
            "response_samples": 0,
        }

    for row in entries:
        extra = row.get("extra_data") or {}
        if not isinstance(extra, dict):
            extra = {}

        haystack_parts = [
            str(row.get("message") or ""),
            str(row.get("url") or ""),
            str(extra.get("action") or ""),
            str(extra.get("endpoint") or ""),
            str(extra.get("service") or ""),
            str(extra.get("request_url") or ""),
        ]
        haystack = " ".join(haystack_parts).lower()

        matched_key = _match_runtime_metric_key(token_map, haystack)
        if matched_key is None:
            continue

        item = metrics[matched_key]
        item["hits"] += 1
        admin_blocked = _is_admin_block_log(extra, row.get("message"))
        if admin_blocked:
            item["admin_blocked"] += 1
            continue

        failed = _is_failure_log(row.get("log_level"), extra, row.get("message"))
        if failed:
            item["failures"] += 1
        else:
            item["successes"] += 1

        response_ms = _extract_response_time_ms(extra)
        if response_ms is not None:
            item["response_total_ms"] += response_ms
            item["response_samples"] += 1

    result = {}
    for key, item in metrics.items():
        avg = None
        if item["response_samples"] > 0:
            avg = round(item["response_total_ms"] / item["response_samples"], 1)
        effective_hits = max(item["hits"] - item["admin_blocked"], 0)
        success_rate = round((item["successes"] / effective_hits) * 100, 1) if effective_hits else 0.0
        result[key] = {
            "hits": item["hits"],
            "failures": item["failures"],
            "successes": item["successes"],
            "admin_blocked": item["admin_blocked"],
            "success_rate": success_rate,
            "avg_response_ms": avg,
        }
    return result


def _collect_runtime_trend_7d(by_vendor, endpoint_usage_by_api):
    now = timezone.now()
    since = now - timedelta(days=7)
    entries = (
        LogEntry.objects
        .filter(timestamp__gte=since)
        .values("timestamp", "log_level", "message", "url", "extra_data")
    )

    token_map = _build_runtime_token_map(by_vendor, endpoint_usage_by_api)
    days = []
    day_index = {}
    for offset in range(6, -1, -1):
        day = timezone.localtime(now - timedelta(days=offset))
        key = day.date().isoformat()
        days.append(
            {
                "date": key,
                "label": day.strftime("%a"),
                "hits": 0,
                "successes": 0,
                "failures": 0,
                "admin_blocked": 0,
                "success_rate": 0.0,
            }
        )
        day_index[key] = len(days) - 1

    for row in entries:
        extra = row.get("extra_data") or {}
        if not isinstance(extra, dict):
            extra = {}
        haystack_parts = [
            str(row.get("message") or ""),
            str(row.get("url") or ""),
            str(extra.get("action") or ""),
            str(extra.get("endpoint") or ""),
            str(extra.get("service") or ""),
            str(extra.get("request_url") or ""),
        ]
        haystack = " ".join(haystack_parts).lower()
        if _match_runtime_metric_key(token_map, haystack) is None:
            continue

        ts = row.get("timestamp")
        if ts is None:
            continue
        day_key = timezone.localtime(ts).date().isoformat()
        idx = day_index.get(day_key)
        if idx is None:
            continue

        item = days[idx]
        item["hits"] += 1
        if _is_admin_block_log(extra, row.get("message")):
            item["admin_blocked"] += 1
            continue
        if _is_failure_log(row.get("log_level"), extra, row.get("message")):
            item["failures"] += 1
        else:
            item["successes"] += 1

    max_hits = max([d.get("hits", 0) for d in days], default=0)
    for item in days:
        effective_hits = max(item["hits"] - item["admin_blocked"], 0)
        item["success_rate"] = round((item["successes"] / effective_hits) * 100, 1) if effective_hits else 0.0
        item["hit_bar_pct"] = round((item["hits"] / max_hits) * 100, 1) if max_hits else 0.0
        item["failure_mix_pct"] = round((item["failures"] / item["hits"]) * 100, 1) if item["hits"] else 0.0
    return days


def _is_admin_block_log(extra_data, message):
    msg = str(message or "").upper()
    if "AD400" in msg:
        return True
    error_code = str(extra_data.get("error") or "").upper()
    if error_code == "AD400":
        return True
    for err in extra_data.get("errors") or []:
        if isinstance(err, dict) and str(err.get("code") or "").upper() == "AD400":
            return True
    return False


def _is_failure_log(log_level, extra_data, message):
    level = str(log_level or "").upper()
    if level in {"ERROR", "CRITICAL"}:
        return True
    status_code = extra_data.get("status_code") or extra_data.get("response_status_code")
    try:
        if status_code is not None and int(status_code) >= 400:
            return True
    except (TypeError, ValueError):
        pass
    success_value = extra_data.get("success")
    if success_value is False:
        return True
    msg = str(message or "").lower()
    if " failed" in msg or " error" in msg or "exception" in msg:
        return True
    return False


def _extract_response_time_ms(extra_data):
    for key in ("response_time_ms", "duration_ms", "latency_ms"):
        value = extra_data.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _pick_best_api(apis):
    candidates = [a for a in apis if a.get("daily_hits", 0) > 0]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda a: (
            -(a.get("success_rate_24h") or 0),
            (a.get("avg_response_ms_24h") if a.get("avg_response_ms_24h") is not None else 10**9),
            -(a.get("daily_hits") or 0),
        ),
    )[0]


class ServicesIntegratedView(TemplateView):
    """
    GET /services/
    Integrated vendors & services (from ServiceFlowStep).
    """
    template_name = "portal/services/integrated.html"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not _is_services_admin(request.user):
            messages.error(request, "Access denied. Admin or Super Admin required.")
            return redirect("/dashboard/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        endpoint_usage_by_api = _collect_v2_api_endpoint_usage()

        # (1) Base vendors and vendor APIs (works even when flow steps are not configured)
        vendor_rows = list(
            ApiVendor.objects
            .values("code", "name", "is_active", "description")
            .order_by("name")
        )
        vendor_api_rows = list(
            VendorApi.objects
            .values("vendor__code", "api_code", "name", "purpose", "is_active")
            .order_by("vendor__code", "api_code")
        )

        by_vendor = {}
        for v in vendor_rows:
            by_vendor[v["code"]] = {
                "name": v["name"],
                "code": v["code"],
                "is_active": bool(v["is_active"]),
                "description": (v["description"] or "").strip(),
                "services": [],
                "apis": [],
            }

        # (2) Integrated services from flow steps (if configured)
        steps = (
            ServiceFlowStep.objects
            .select_related("vendor", "service")
            .values(
                "vendor_id",
                "vendor__code",
                "vendor__name",
                "vendor__is_active",
                "vendor__description",
                "service_id",
                "service__code",
                "service__name",
                "service__description",
                "vendor_api__api_code",
                "vendor_api__name",
                "vendor_api__is_active",
            )
            .distinct()
        )
        api_services_map = {}
        for s in steps:
            api_code = s.get("vendor_api__api_code")
            service_code = s.get("service__code")
            if not api_code or not service_code:
                continue
            if api_code not in api_services_map:
                api_services_map[api_code] = set()
            api_services_map[api_code].add(service_code)

        # Group by vendor from step data
        for s in steps:
            vcode = s["vendor__code"]
            if vcode not in by_vendor:
                by_vendor[vcode] = {
                    "name": s["vendor__name"],
                    "code": vcode,
                    "is_active": bool(s["vendor__is_active"]),
                    "description": (s["vendor__description"] or "").strip(),
                    "services": [],
                    "apis": [],
                }
            by_vendor[vcode]["services"].append({
                "code": s["service__code"],
                "name": s["service__name"],
                "description": (s["service__description"] or "").strip(),
            })
            if s.get("vendor_api__api_code"):
                by_vendor[vcode]["apis"].append({
                    "code": s["vendor_api__api_code"],
                    "name": s.get("vendor_api__name") or s["vendor_api__api_code"],
                    "purpose": "",
                    "is_active": bool(s.get("vendor_api__is_active")),
                })

        # Add vendor APIs directly (fallback when steps are empty)
        for api in vendor_api_rows:
            vcode = api["vendor__code"]
            if vcode not in by_vendor:
                continue
            by_vendor[vcode]["apis"].append({
                "code": api["api_code"],
                "name": api["name"],
                "purpose": (api["purpose"] or "").strip(),
                "is_active": bool(api.get("is_active")),
            })

        runtime_metrics = _collect_api_runtime_metrics(by_vendor, endpoint_usage_by_api)
        trend_7d = _collect_runtime_trend_7d(by_vendor, endpoint_usage_by_api)

        # Dedupe services/APIs per vendor
        for v in by_vendor.values():
            seen_services = set()
            unique = []
            for svc in v["services"]:
                key = svc["code"]
                if key not in seen_services:
                    seen_services.add(key)
                    unique.append(svc)
            v["services"] = unique

            seen_apis = set()
            unique_apis = []
            for api in v["apis"]:
                key = api["code"]
                if key not in seen_apis:
                    seen_apis.add(key)
                    unique_apis.append(api)
            v["apis"] = unique_apis
            for api in v["apis"]:
                service_links = sorted(list(api_services_map.get(api["code"], set())))
                endpoint_links = [
                    link for link in endpoint_usage_by_api.get(api["code"], [])
                    if not link.get("vendor_hints") or v["code"] in link.get("vendor_hints", [])
                ]
                perf = runtime_metrics.get((v["code"], api["code"]), {})
                api["service_links"] = service_links
                api["endpoint_links"] = endpoint_links
                api["usage_count"] = len(service_links) + len(endpoint_links)
                api["impact_note"] = _build_api_impact_note(api)
                api["is_used"] = api["usage_count"] > 0
                api["daily_hits"] = perf.get("hits", 0)
                api["daily_failures"] = perf.get("failures", 0)
                api["daily_successes"] = perf.get("successes", 0)
                api["admin_blocked_24h"] = perf.get("admin_blocked", 0)
                api["success_rate_24h"] = perf.get("success_rate", 0.0)
                api["avg_response_ms_24h"] = perf.get("avg_response_ms")
            v["api_count"] = len(unique_apis)
            v["used_api_count"] = sum(1 for a in v["apis"] if a.get("is_used"))
            v["daily_hits"] = sum(a.get("daily_hits", 0) for a in v["apis"])
            v["daily_failures"] = sum(a.get("daily_failures", 0) for a in v["apis"])
            v["admin_blocked_24h"] = sum(a.get("admin_blocked_24h", 0) for a in v["apis"])
            v["daily_successes"] = sum(a.get("daily_successes", 0) for a in v["apis"])
            effective_hits = max(v["daily_hits"] - v["admin_blocked_24h"], 0)
            v["success_rate_24h"] = round((v["daily_successes"] / effective_hits) * 100, 1) if effective_hits else 0.0
            avg_samples = [a.get("avg_response_ms_24h") for a in v["apis"] if a.get("avg_response_ms_24h") is not None]
            v["avg_response_ms_24h"] = round(sum(avg_samples) / len(avg_samples), 1) if avg_samples else None
            v["top_api_24h"] = _pick_best_api(v["apis"])
            v["narration"] = _build_vendor_narration(v)

        vendors_integrated = sorted(
            [v for v in by_vendor.values() if v.get("api_count", 0) > 0 or v.get("services")],
            key=lambda x: x["name"]
        )
        total_services = len({svc["code"] for v in vendors_integrated for svc in v["services"]})
        total_apis = sum(v.get("api_count", 0) for v in vendors_integrated)
        used_apis = sum(v.get("used_api_count", 0) for v in vendors_integrated)
        total_daily_hits = sum(v.get("daily_hits", 0) for v in vendors_integrated)
        total_daily_failures = sum(v.get("daily_failures", 0) for v in vendors_integrated)
        total_admin_blocked = sum(v.get("admin_blocked_24h", 0) for v in vendors_integrated)
        total_daily_successes = sum(v.get("daily_successes", 0) for v in vendors_integrated)
        total_effective_hits = max(total_daily_hits - total_admin_blocked, 0)
        health_success_pct = round((total_daily_successes / total_daily_hits) * 100, 1) if total_daily_hits else 0.0
        health_failure_pct = round((total_daily_failures / total_daily_hits) * 100, 1) if total_daily_hits else 0.0
        health_ad400_pct = round((total_admin_blocked / total_daily_hits) * 100, 1) if total_daily_hits else 0.0
        overall_success_rate = round((total_daily_successes / total_effective_hits) * 100, 1) if total_effective_hits else 0.0
        best_api_today = _pick_best_api([api for vendor in vendors_integrated for api in vendor.get("apis", [])])
        active_vendors = sum(1 for v in vendors_integrated if v.get("is_active"))
        all_apis = [api for vendor in vendors_integrated for api in vendor.get("apis", [])]
        top_apis_24h = sorted(
            all_apis,
            key=lambda a: (-(a.get("daily_hits") or 0), -(a.get("success_rate_24h") or 0)),
        )[:6]
        max_top_api_hits = max([a.get("daily_hits", 0) for a in top_apis_24h], default=0)
        for api in top_apis_24h:
            hits = api.get("daily_hits", 0)
            api["hit_bar_pct"] = round((hits / max_top_api_hits) * 100, 1) if max_top_api_hits else 0.0

        vendor_health_24h = sorted(
            [
                {
                    "name": v["name"],
                    "code": v["code"],
                    "hits": v.get("daily_hits", 0),
                    "failures": v.get("daily_failures", 0),
                    "admin_blocked": v.get("admin_blocked_24h", 0),
                    "success_rate": v.get("success_rate_24h", 0.0),
                }
                for v in vendors_integrated
            ],
            key=lambda r: (-r["hits"], -r["success_rate"]),
        )[:8]

        mapped_ratio = round((used_apis / total_apis) * 100, 1) if total_apis else 0.0
        active_vendor_ratio = round((active_vendors / len(vendors_integrated)) * 100, 1) if vendors_integrated else 0.0
        readiness_score = round((overall_success_rate * 0.6) + (mapped_ratio * 0.25) + (active_vendor_ratio * 0.15), 1)
        weekly_hits = sum(day.get("hits", 0) for day in trend_7d)
        weekly_failures = sum(day.get("failures", 0) for day in trend_7d)
        weekly_admin_blocked = sum(day.get("admin_blocked", 0) for day in trend_7d)
        weekly_effective_hits = max(weekly_hits - weekly_admin_blocked, 0)
        weekly_successes = sum(day.get("successes", 0) for day in trend_7d)
        weekly_success_rate = round((weekly_successes / weekly_effective_hits) * 100, 1) if weekly_effective_hits else 0.0
        hit_run_rate = round(weekly_hits / 7, 1) if trend_7d else 0.0
        last_day_hits = trend_7d[-1]["hits"] if trend_7d else 0
        prev_day_hits = trend_7d[-2]["hits"] if len(trend_7d) > 1 else 0
        traffic_delta_pct = 0.0
        if prev_day_hits > 0:
            traffic_delta_pct = round(((last_day_hits - prev_day_hits) / prev_day_hits) * 100, 1)
        elif last_day_hits > 0:
            traffic_delta_pct = 100.0

        ctx["vendors_integrated"] = vendors_integrated
        ctx["vendors_stats"] = {
            "total": len(vendors_integrated),
            "active": active_vendors,
            "inactive": max(len(vendors_integrated) - active_vendors, 0),
            "services": total_services,
            "apis": total_apis,
            "used_apis": used_apis,
            "daily_hits": total_daily_hits,
            "daily_failures": total_daily_failures,
            "admin_blocked_24h": total_admin_blocked,
            "daily_successes": total_daily_successes,
            "effective_hits_24h": total_effective_hits,
            "overall_success_rate_24h": overall_success_rate,
            "mapped_ratio_24h": mapped_ratio,
            "readiness_score_24h": readiness_score,
            "health_success_pct_24h": health_success_pct,
            "health_failure_pct_24h": health_failure_pct,
            "health_ad400_pct_24h": health_ad400_pct,
            "weekly_hits": weekly_hits,
            "weekly_failures": weekly_failures,
            "weekly_admin_blocked": weekly_admin_blocked,
            "weekly_success_rate": weekly_success_rate,
            "daily_run_rate_7d": hit_run_rate,
            "traffic_delta_pct": traffic_delta_pct,
            "best_api_today": (
                f"{best_api_today['code']} ({best_api_today['success_rate_24h']}%)"
                if best_api_today
                else "No traffic detected in last 24h"
            ),
        }
        ctx["top_apis_24h"] = top_apis_24h
        ctx["vendor_health_24h"] = vendor_health_24h
        ctx["trend_7d"] = trend_7d
        ctx["platform"] = (self.request.GET.get("platform") or "").strip().lower()
        if ctx["platform"] not in ("parkpe", "payswap"):
            ctx["platform"] = None

        return ctx


def _build_vendor_narration(vendor_row):
    if vendor_row.get("description"):
        return vendor_row["description"]

    service_lines = []
    for svc in vendor_row.get("services", []):
        service_lines.append(SERVICE_NARRATION_BY_CODE.get(svc["code"], svc.get("description") or f"{svc['name']} workflows."))

    unique_lines = []
    seen = set()
    for line in service_lines:
        clean = (line or "").strip()
        if not clean:
            continue
        if clean not in seen:
            seen.add(clean)
            unique_lines.append(clean)

    if not unique_lines and vendor_row.get("apis"):
        first_api = vendor_row["apis"][0]
        if first_api.get("purpose"):
            return first_api["purpose"]
        return f"{first_api.get('name') or first_api.get('code')} API operations."
    if not unique_lines:
        return "Supports integrated service orchestration workflows."
    if len(unique_lines) == 1:
        return unique_lines[0]
    return f"{unique_lines[0]} Also used for {unique_lines[1].rstrip('.').lower()}."


def _build_api_impact_note(api_row):
    service_links = api_row.get("service_links", [])
    endpoint_links = api_row.get("endpoint_links", [])

    impact_parts = []
    if service_links:
        impact_parts.append(f"Service flows impacted: {', '.join(service_links)}")
    if endpoint_links:
        routes = ", ".join(link["route"] for link in endpoint_links[:2])
        if len(endpoint_links) > 2:
            routes = f"{routes} +{len(endpoint_links) - 2} more"
        impact_parts.append(f"Partner endpoints impacted: {routes}")
    if not impact_parts:
        return "No explicit flow or endpoint mapping found yet (configured API only)."
    return " | ".join(impact_parts)


@require_POST
@login_required
def toggle_vendor_status_view(request, vendor_code):
    if not _is_services_admin(request.user):
        return JsonResponse({"success": False, "message": "Access denied."}, status=403)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON payload."}, status=400)

    if "enabled" not in payload:
        return JsonResponse({"success": False, "message": "Missing 'enabled' field."}, status=400)

    enabled = bool(payload.get("enabled"))

    try:
        vendor = ApiVendor.objects.get(code=vendor_code)
    except ApiVendor.DoesNotExist:
        return JsonResponse({"success": False, "message": "Vendor not found."}, status=404)

    vendor.is_active = enabled
    vendor.save(update_fields=["is_active", "updated_at"])

    return JsonResponse(
        {
            "success": True,
            "vendor_code": vendor.code,
            "is_active": vendor.is_active,
            "message": f"{vendor.name} is now {'ON' if vendor.is_active else 'OFF'}.",
        }
    )


@require_POST
@login_required
def toggle_vendor_api_status_view(request, vendor_code, api_code):
    if not _is_services_admin(request.user):
        return JsonResponse({"success": False, "message": "Access denied."}, status=403)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON payload."}, status=400)

    if "enabled" not in payload:
        return JsonResponse({"success": False, "message": "Missing 'enabled' field."}, status=400)

    enabled = bool(payload.get("enabled"))

    try:
        vendor_api = VendorApi.objects.select_related("vendor").get(vendor__code=vendor_code, api_code=api_code)
    except VendorApi.DoesNotExist:
        return JsonResponse({"success": False, "message": "Vendor API not found."}, status=404)

    vendor_api.is_active = enabled
    vendor_api.save(update_fields=["is_active", "updated_at"])

    return JsonResponse(
        {
            "success": True,
            "vendor_code": vendor_code,
            "api_code": api_code,
            "is_active": vendor_api.is_active,
            "message": f"{vendor_api.name} is now {'ON' if vendor_api.is_active else 'OFF'}.",
        }
    )
