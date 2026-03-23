"""
Log management views: list, export, detail, resolve.
"""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView, DetailView
from django.http import JsonResponse
from django.db import models

from portal.models import LogEntry, User


def _parse_bbps_consumer_details(extra_data):
    """
    Parse BBPS View Bill / Fetch Bill response from extra_data.response_body
    and return structured consumer details for display.
    Returns list of dicts with label/value for template, or None if not parseable.
    """
    if not extra_data or not isinstance(extra_data, dict):
        return None
    # response_body can be JSON string or response_body_truncated_sanitized
    raw = extra_data.get("response_body") or extra_data.get("response_body_truncated_sanitized")
    if not raw:
        return None
    try:
        if isinstance(raw, str):
            data = json.loads(raw)
        elif isinstance(raw, dict):
            data = raw
        else:
            return None
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    # BBPS success: {"success": true, "data": [...]} or {"data": {...}} or {"billDetails": [...]}
    if data.get("success") is False:
        return None
    # Extract bill details array/object
    inner = data.get("data")
    bill_list = None
    if isinstance(inner, list) and inner:
        bill_list = inner
    elif isinstance(inner, dict):
        bill_list = inner.get("billDetails") or inner.get("bill_details") or inner.get("data")
        if isinstance(bill_list, dict):
            bill_list = [bill_list]
        elif not isinstance(bill_list, list) or not bill_list:
            bill_list = [inner]
    elif inner is None:
        bill_list = data.get("billDetails") or data.get("bill_details")
        if isinstance(bill_list, dict):
            bill_list = [bill_list]
        elif isinstance(bill_list, list) and bill_list:
            pass
        elif any(k in data for k in ("billAmount", "bill_amount", "userName", "user_name", "amount")):
            bill_list = [data]
        else:
            bill_list = None
    if not bill_list or not isinstance(bill_list, list):
        return None
    # Map common BBPS field names to display labels
    FIELD_MAP = [
        ("billAmount", "Bill Amount"),
        ("bill_amount", "Bill Amount"),
        ("amount", "Amount"),
        ("dueDate", "Due Date"),
        ("due_date", "Due Date"),
        ("userName", "Consumer Name"),
        ("user_name", "Consumer Name"),
        ("consumerName", "Consumer Name"),
        ("customerName", "Customer Name"),
        ("cellNumber", "Mobile Number"),
        ("cell_number", "Mobile Number"),
        ("mobile", "Mobile"),
        ("billdate", "Bill Date"),
        ("bill_date", "Bill Date"),
        ("accountNumber", "Account Number"),
        ("account_number", "Account Number"),
        ("customerId", "Customer ID"),
        ("customer_id", "Customer ID"),
    ]
    result = []
    for item in bill_list:
        if not isinstance(item, dict):
            continue
        rows = []
        seen = set()
        for key, label in FIELD_MAP:
            val = item.get(key)
            if val is not None and val != "" and label.lower() not in seen:
                seen.add(label.lower())
                rows.append({"label": label, "value": val})
        # Include any other non-empty keys not in FIELD_MAP (generic fallback)
        for k, v in item.items():
            if k in ("billAmount", "bill_amount", "amount", "dueDate", "due_date",
                     "userName", "user_name", "consumerName", "customerName",
                     "cellNumber", "cell_number", "mobile", "billdate", "bill_date",
                     "accountNumber", "account_number", "customerId", "customer_id"):
                continue
            if v is not None and v != "" and isinstance(v, (str, int, float)):
                label = k.replace("_", " ").title()
                rows.append({"label": label, "value": v})
        if rows:
            result.append(rows)
    return result if result else None


class LogListView(ListView):
    """View to list and filter log entries"""
    model = LogEntry
    template_name = 'portal/logs/list.html'
    context_object_name = 'logs'
    paginate_by = 50

    def get_paginate_by(self, queryset):
        per_page = self.request.GET.get('per_page', '50')
        try:
            return int(per_page)
        except (ValueError, TypeError):
            return 50

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return redirect('/signin/')
        if not self.request.user.is_staff:
            messages.error(self.request, 'You do not have permission to view logs.')
            return redirect('/dashboard/')
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        queryset = LogEntry.objects.all()
        log_level = self.request.GET.get('log_level')
        if log_level:
            queryset = queryset.filter(log_level=log_level)
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category=category)
        resolved = self.request.GET.get('resolved')
        if resolved == 'true':
            queryset = queryset.filter(
                log_level__in=['ERROR', 'CRITICAL'],
                resolved=True
            )
        elif resolved == 'false':
            queryset = queryset.filter(
                log_level__in=['ERROR', 'CRITICAL'],
                resolved=False
            )
        user_id = self.request.GET.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(message__icontains=search) |
                models.Q(module_name__icontains=search) |
                models.Q(url__icontains=search) |
                models.Q(request_id__icontains=search)
            )
        return queryset.order_by('-timestamp')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_logs'] = LogEntry.objects.count()
        context['error_logs'] = LogEntry.objects.filter(log_level='ERROR').count()
        context['warning_logs'] = LogEntry.objects.filter(log_level='WARNING').count()
        context['unresolved_logs'] = LogEntry.objects.filter(
            log_level__in=['ERROR', 'CRITICAL'],
            resolved=False
        ).count()
        context['log_levels'] = LogEntry.LOG_LEVEL_CHOICES
        context['categories'] = LogEntry.CATEGORY_CHOICES
        context['users'] = User.objects.filter(
            log_entries__isnull=False
        ).distinct().order_by('username')
        context['current_per_page'] = self.get_paginate_by(self.get_queryset())
        return context

    def get(self, request, *args, **kwargs):
        if request.GET.get('format') == 'json':
            queryset = self.get_queryset()
            page_size = self.paginate_by
            paginator = self.get_paginator(queryset, page_size)
            page_number = request.GET.get('page', 1)
            page_obj = paginator.get_page(page_number)
            logs_data = []
            for log in page_obj:
                logs_data.append({
                    'id': log.id,
                    'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else '',
                    'log_level': log.log_level or '',
                    'category': log.get_category_display() if log.category else '',
                    'message': log.message or '',
                    'message_short': log.message[:100] + '...' if log.message and len(log.message) > 100 else (log.message or ''),
                    'module_name': log.module_name or '',
                    'url': log.url or '',
                    'user': log.user.username if log.user else '',
                    'resolved': log.resolved,
                    'resolved_at': log.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if log.resolved_at else '',
                    'resolved_by': log.resolved_by.username if log.resolved_by else '',
                })
            return JsonResponse({
                'logs': logs_data,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'page_number': page_obj.number,
                'num_pages': paginator.num_pages,
                'total_count': paginator.count,
                'per_page': self.get_paginate_by(queryset),
                'start_index': page_obj.start_index(),
                'end_index': page_obj.end_index(),
            })
        return super().get(request, *args, **kwargs)


@login_required
def debug_voucher_logs(request):
    """Debug view to check voucher log status"""
    from django.db.models import Count
    from django.utils import timezone
    from datetime import timedelta

    total_logs = LogEntry.objects.count()
    gift_voucher_logs = LogEntry.objects.filter(category='gift_voucher')
    gift_voucher_count = gift_voucher_logs.count()
    recent_gift_voucher_logs = gift_voucher_logs.filter(
        timestamp__gte=timezone.now() - timedelta(hours=24)
    ).count()
    categories = LogEntry.objects.values('category').annotate(
        count=Count('id')
    ).order_by('-count')
    recent_logs = gift_voucher_logs.order_by('-timestamp')[:20]
    all_recent = LogEntry.objects.filter(
        timestamp__gte=timezone.now() - timedelta(hours=24)
    ).order_by('-timestamp')[:50]
    voucher_related_logs = []
    for log in all_recent:
        if log.extra_data and isinstance(log.extra_data, dict):
            operation = log.extra_data.get('operation', '')
            if any(x in str(operation).lower() for x in ['voucher', 'batch', 'client', 'brand', 'onboarding']):
                voucher_related_logs.append(log)
    celery_running = False
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        active_workers = inspect.active()
        celery_running = active_workers is not None and len(active_workers) > 0
    except Exception:
        pass
    context = {
        'total_logs': total_logs,
        'gift_voucher_logs': gift_voucher_count,
        'recent_gift_voucher_logs': recent_gift_voucher_logs,
        'categories': categories,
        'recent_logs': recent_logs,
        'voucher_related_logs': voucher_related_logs[:10],
        'celery_running': celery_running,
    }
    return render(request, 'portal/logs/debug.html', context)


class LogExportView(View):
    """Export logs to CSV"""

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return redirect('/signin/')
        if not self.request.user.is_staff:
            messages.error(self.request, 'You do not have permission to export logs.')
            return redirect('/dashboard/')
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        queryset = LogEntry.objects.all()
        log_level = self.request.GET.get('log_level')
        if log_level:
            queryset = queryset.filter(log_level=log_level)
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category=category)
        resolved = self.request.GET.get('resolved')
        if resolved == 'true':
            queryset = queryset.filter(
                log_level__in=['ERROR', 'CRITICAL'],
                resolved=True
            )
        elif resolved == 'false':
            queryset = queryset.filter(
                log_level__in=['ERROR', 'CRITICAL'],
                resolved=False
            )
        user_id = self.request.GET.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(message__icontains=search) |
                models.Q(module_name__icontains=search) |
                models.Q(url__icontains=search) |
                models.Q(request_id__icontains=search)
            )
        return queryset.order_by('-timestamp')

    def get(self, request):
        import csv
        from django.http import HttpResponse
        from django.utils import timezone
        import json

        queryset = self.get_queryset()
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f'logs_export_{timestamp}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Timestamp', 'Log Level', 'Category', 'Message', 'Module', 'URL',
            'User', 'Request ID', 'Response ID', 'Client IP', 'Session ID',
            'Resolved', 'Resolved At', 'Resolved By', 'Exception Type', 'Extra Data'
        ])
        for log in queryset:
            extra_data_str = ''
            if log.extra_data:
                try:
                    extra_data_str = json.dumps(log.extra_data, ensure_ascii=False)
                except Exception:
                    extra_data_str = str(log.extra_data)
            writer.writerow([
                log.id,
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else '',
                log.log_level or '',
                log.get_category_display() if log.category else '',
                log.message or '',
                log.module_name or '',
                log.url or '',
                log.user.username if log.user else '',
                log.request_id or '',
                log.response_id or '',
                str(log.client_ip) if log.client_ip else '',
                log.session_id or '',
                'Yes' if log.resolved else 'No',
                log.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if log.resolved_at else '',
                log.resolved_by.username if log.resolved_by else '',
                log.exception_type or '',
                extra_data_str
            ])
        return response


class LogDetailView(DetailView):
    """View to see detailed log entry"""
    model = LogEntry
    template_name = 'portal/logs/detail.html'
    context_object_name = 'log'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return redirect('/signin/')
        if not self.request.user.is_staff:
            messages.error(self.request, 'You do not have permission to view logs.')
            return redirect('/dashboard/')
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        log_entry = self.get_object()
        if log_entry.category == 'cashfree':
            try:
                from portal.models import CashfreeAPILog
                cashfree_log = CashfreeAPILog.objects.filter(log_entry=log_entry).first()
                if not cashfree_log and log_entry.request_id:
                    cashfree_log = CashfreeAPILog.objects.filter(request_id=log_entry.request_id).first()
                context['cashfree_log'] = cashfree_log
            except Exception:
                context['cashfree_log'] = None
        else:
            context['cashfree_log'] = None
        # For BBPS logs without api_name (e.g. old Parkpe logs), derive from message so detail page shows which API
        extra = getattr(log_entry, 'extra_data', None) or {}
        if (log_entry.category in ('parkpe_bbps', 'mobikwik_bbps', 'euronet_bbps') and
                not extra.get('api_name') and not extra.get('action') and log_entry.message):
            msg_lower = log_entry.message.lower()
            if 'fetch bill' in msg_lower or 'bill fetch' in msg_lower:
                context['log_display_api_name'] = 'Fetch Bill'
            elif ('pay' in msg_lower and 'cart' not in msg_lower) or 'pay bill' in msg_lower:
                context['log_display_api_name'] = 'Pay Bill'
            elif 'payment status' in msg_lower or 'status fetch' in msg_lower:
                context['log_display_api_name'] = 'Payment Status'
            elif 'categor' in msg_lower:
                context['log_display_api_name'] = 'Categories'
            elif 'operator' in msg_lower or 'biller' in msg_lower:
                context['log_display_api_name'] = 'Get Operators'
            else:
                context['log_display_api_name'] = (log_entry.message[:50] + '…') if len(log_entry.message) > 50 else log_entry.message
        else:
            context['log_display_api_name'] = None
        # Consumer details for BBPS View Bill / Fetch Bill (parse response_body)
        bbps_bill_actions = ("view_bill", "validation", "fetch_bill")
        if (log_entry.category in ("parkpe_bbps", "mobikwik_bbps", "euronet_bbps") and
                extra.get("action") in bbps_bill_actions and extra.get("success")):
            context["consumer_details"] = _parse_bbps_consumer_details(extra)
        else:
            context["consumer_details"] = None
        # Related logs with same request_id (ParkPe → Vendor flow: did vendor get hit?)
        if log_entry.request_id:
            context["related_logs_same_request"] = list(
                LogEntry.objects.filter(request_id=log_entry.request_id)
                .exclude(pk=log_entry.pk)
                .order_by("timestamp")[:20]
            )
            # Whether any of them is a vendor call (mobikwik_bbps / euronet_bbps)
            context["vendor_was_called"] = any(
                log.category in ("mobikwik_bbps", "euronet_bbps")
                for log in context["related_logs_same_request"]
            )
        else:
            context["related_logs_same_request"] = []
            context["vendor_was_called"] = None
        return context

    def post(self, request, *args, **kwargs):
        log = self.get_object()
        action = request.POST.get('action')
        if action == 'resolve':
            notes = request.POST.get('notes', '')
            log.mark_resolved(resolved_by=request.user, notes=notes)
            messages.success(request, 'Log entry marked as resolved.')
        elif action == 'unresolve':
            log.mark_unresolved()
            messages.success(request, 'Log entry marked as unresolved.')
        return redirect('log_detail', pk=log.pk)


@login_required
def log_resolve_view(request, log_id):
    """Quick resolve/unresolve log entry"""
    if not request.user.is_authenticated:
        messages.error(request, 'Please login to access logs.')
        return redirect('/signin/')
    if not request.user.is_staff:
        messages.error(request, 'You do not have permission to manage logs.')
        return redirect('/dashboard/')
    log = get_object_or_404(LogEntry, id=log_id)
    action = request.POST.get('action')
    if action == 'resolve':
        notes = request.POST.get('notes', '')
        log.mark_resolved(resolved_by=request.user, notes=notes)
        messages.success(request, 'Log entry marked as resolved.')
    elif action == 'unresolve':
        log.mark_unresolved()
        messages.success(request, 'Log entry marked as unresolved.')
    return redirect(request.META.get('HTTP_REFERER', '/logs/'))
