"""
Portal dashboard views – base and role-specific dashboards.
"""
from datetime import timedelta, datetime
from decimal import Decimal

from django.shortcuts import redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.views import View
from django.http import JsonResponse
from django.db.models import Sum, Q, Count, Case, When, DecimalField, Value
from django.db.models.functions import Coalesce

from portal.models import User, Profile, KYC, Wallet, ParkPeVoucherTransaction, ParkPePaymentOrder, ApiVendor
from portal.decorators import log_view_action
from portal.utils.logging_helper import get_logger
from core.config import payswap_config

logger = get_logger('portal.views')


class DashboardView(TemplateView):
    """Dashboard view - redirects to role-specific dashboard"""
    template_name = 'portal/dashboard/base.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    @method_decorator(log_view_action(action='view_dashboard', resource='dashboard'))
    def get(self, request):
        user = request.user
        # Staff / super-admin / admin users go to super dashboard (admin dashboard was removed)
        role_code_raw = getattr(user, 'role_code', None) or ''
        role_code = role_code_raw.lower() if role_code_raw else 'customer'
        if getattr(user, 'is_staff', False) or role_code in ('super_admin', 'admin'):
            return redirect('/dashboard/super/')
        dashboard_map = {
            'super_admin': 'super',
            'admin': 'admin',
            'employee': 'employee',
            'super_distributor': 'distributor',
            'distributor': 'distributor',
            'retailer': 'retailer',
            'customer': 'customer',
        }
        dashboard_name = dashboard_map.get(role_code, 'customer')
        return redirect(f'/dashboard/{dashboard_name}/')


class EmployeeDashboardView(TemplateView):
    """Employee dashboard"""
    template_name = 'portal/dashboard/employee.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class SuperDashboardView(TemplateView):
    """Super dashboard - same stats and quick actions as Admin for system-wide access"""
    template_name = 'portal/dashboard/super.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_users'] = User.objects.count()
        context['pending_kyc'] = KYC.objects.filter(status='pending').count()
        context['total_wallets'] = Wallet.objects.count()
        context['active_profiles'] = Profile.objects.filter(status='active').count()
        context['vendor_pool_balances'] = _get_vendor_pool_balances()
        try:
            from portal.models import ResellerPartner, ResellerPartnerTransaction
            partners = ResellerPartner.objects.all()
            context['total_partners'] = partners.count()
            context['active_partners'] = partners.filter(status='ACTIVE', onboarding_status='APPROVED').count()
            context['pending_partner_onboarding'] = partners.filter(onboarding_status='PENDING').count()
            last_30d = timezone.now() - timedelta(days=30)
            financial_summary = ResellerPartnerTransaction.objects.filter(
                transaction_date__gte=last_30d,
                status='COMPLETED'
            ).aggregate(
                total_revenue=Sum('amount', filter=Q(transaction_type='REVENUE')),
                total_commission=Sum('commission_amount', filter=Q(transaction_type='COMMISSION'))
            )
            context['partner_revenue_30d'] = financial_summary.get('total_revenue') or 0
            context['partner_commission_30d'] = financial_summary.get('total_commission') or 0
            context['recent_partners'] = partners.select_related('wallet').order_by('-created_at')[:5]
        except Exception as e:
            logger.error(f'Error loading partner stats for super dashboard: {str(e)}')
            context['total_partners'] = 0
            context['active_partners'] = 0
            context['pending_partner_onboarding'] = 0
            context['partner_revenue_30d'] = 0
            context['partner_commission_30d'] = 0
            context['recent_partners'] = []
        return context


def _get_vendor_pool_balances():
    """Fetch vendor pool balance cards for dashboard."""
    def _extract_instantpay_business_balance(payload):
        """Extract business wallet balance (strict closingBalance first)."""
        if not isinstance(payload, dict):
            return None

        # Strict preference: closing balance from statement response.
        direct_keys = ('closingBalance', 'closing_balance')
        for key in direct_keys:
            value = payload.get(key)
            if value not in (None, ''):
                return value

        # Nested wrappers that vendors commonly use
        for container_key in ('data', 'result', 'statement', 'account', 'wallet'):
            nested = payload.get(container_key)
            if isinstance(nested, dict):
                value = _extract_instantpay_business_balance(nested)
                if value not in (None, ''):
                    return value

        # Statement rows fallback.
        entries = payload.get('entries') or payload.get('transactions') or payload.get('statementRows')
        if isinstance(entries, list) and entries:
            first = entries[0]
            if isinstance(first, dict):
                for key in ('closingBalance', 'closing_balance'):
                    value = first.get(key)
                    if value not in (None, ''):
                        return value
        return None

    vendor_rows = []
    for vendor in ApiVendor.objects.filter(is_active=True).order_by('name'):
        row = {
            'vendor_code': vendor.code,
            'vendor_name': vendor.name,
            'balance': None,
            'available': False,
            'message': 'Pool balance endpoint not integrated for this vendor yet.',
            'currency': 'INR',
        }
        try:
            if vendor.code == 'mobikwik':
                from portal.services.bbps_service import BBPSService
                service = BBPSService(vendor='mobikwik')
                if service.is_available():
                    result = service.balance_check()
                    if result.get('success') and result.get('balance') is not None:
                        row['balance'] = result['balance']
                        row['available'] = True
                        row['message'] = 'Live Mobikwik BBPS pool balance'
                    else:
                        row['message'] = result.get('message') or 'Balance fetch failed'
                else:
                    row['message'] = 'Mobikwik BBPS not configured'
            elif vendor.code == 'instantpay':
                from portal.services.vendors.instantpay import InstantpayClient
                client = InstantpayClient()
                if client.is_configured():
                    account_number = payswap_config.get_instantpay_report_account_number()
                    if not account_number:
                        row['message'] = 'Set INSTANTPAY_REPORT_ACCOUNT_NUMBER in .env'
                        vendor_rows.append(row)
                        continue
                    today = datetime.now().strftime('%Y-%m-%d')
                    result = client.request(
                        'account_statement',
                        {
                            'bankProfileId': payswap_config.get_instantpay_report_bank_profile_id(),
                            'accountNumber': account_number,
                            'externalRef': f"DB{int(datetime.now().timestamp())}",
                            'pagination': {'pageNumber': 1, 'recordsPerPage': 1},
                            'filters': {'txnDateFrom': today, 'txnDateTo': today},
                        },
                    )
                    if result.get('success'):
                        payload = result.get('json') or {}
                        extracted_balance = _extract_instantpay_business_balance(payload)
                        if extracted_balance not in (None, ''):
                            try:
                                row['balance'] = float(Decimal(str(extracted_balance)))
                            except Exception:
                                row['balance'] = extracted_balance
                        if row['balance'] is not None:
                            row['available'] = True
                            row['message'] = 'Live Instantpay business wallet balance (from account statement)'
                        else:
                            row['message'] = 'Instantpay account statement received, but business wallet balance not found'
                    else:
                        row['message'] = result.get('message') or result.get('error') or 'Account statement fetch failed'
                else:
                    row['message'] = 'Instantpay not configured'
            elif vendor.code == 'cashfree_pg':
                from portal.services.vendors.cashfree_pg import fetch_easy_split_vendor_on_demand_balance
                res = fetch_easy_split_vendor_on_demand_balance()
                if res.get('success') and res.get('balance') is not None:
                    row['balance'] = res['balance']
                    row['available'] = True
                    row['message'] = res.get('message') or 'Cashfree Easy Split balance'
                else:
                    row['message'] = res.get('message') or 'Cashfree Easy Split balance fetch failed'
        except Exception as e:
            row['message'] = str(e)[:140]
        vendor_rows.append(row)
    return vendor_rows


class DistributorDashboardView(TemplateView):
    """Distributor dashboard"""
    template_name = 'portal/dashboard/distributor.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class RetailerDashboardView(TemplateView):
    """Retailer dashboard"""
    template_name = 'portal/dashboard/retailer.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class MobikwikBalanceApiView(View):
    """JSON API for Mobikwik retailer balance (used by dashboard refresh button)."""

    @method_decorator(login_required)
    def get(self, request):
        result = {'success': False, 'balance': None, 'error': None}
        try:
            from portal.services.bbps_service import BBPSService
            service = BBPSService(vendor='mobikwik')
            if not service.is_available():
                result['error'] = 'Mobikwik BBPS not configured'
                return JsonResponse(result)
            data = service.balance_check()
            if data.get('success') and data.get('balance') is not None:
                bal = data['balance']
                result['success'] = True
                result['balance'] = float(bal) if isinstance(bal, (Decimal, int, float)) else None
            else:
                result['error'] = data.get('message') or 'Balance fetch failed'
        except Exception as e:
            logger.warning(f'Mobikwik balance API failed: {e}')
            result['error'] = str(e)[:100]
        return JsonResponse(result)


class VendorBalancesApiView(View):
    """JSON API for all vendor pool balances (dashboard cards refresh)."""

    @method_decorator(login_required)
    def get(self, request):
        return JsonResponse({'success': True, 'vendors': _get_vendor_pool_balances()})


class CustomerDashboardView(TemplateView):
    """Customer dashboard"""
    template_name = 'portal/dashboard/customer.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class VendorDashboardView(TemplateView):
    """Vendor dashboard"""
    template_name = 'portal/dashboard/vendor.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


class ParkPeTransactionsReportView(TemplateView):
    """Operational report page for all ParkPe transaction flows."""
    template_name = 'portal/dashboard/parkpe_transactions_report.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def _parse_date(self, raw):
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except Exception:
            return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request

        service_filter = (request.GET.get('service') or '').strip()
        user_filter = (request.GET.get('user') or '').strip()
        order_status_filter = (request.GET.get('order_status') or '').strip().lower()
        from_date = self._parse_date(request.GET.get('from'))
        to_date = self._parse_date(request.GET.get('to'))

        voucher_qs = ParkPeVoucherTransaction.objects.select_related('user').all()
        order_qs = ParkPePaymentOrder.objects.select_related('user').all()

        if service_filter:
            voucher_qs = voucher_qs.filter(service_code__iexact=service_filter)
        if user_filter.isdigit():
            voucher_qs = voucher_qs.filter(user_id=int(user_filter))
            order_qs = order_qs.filter(user_id=int(user_filter))
        if order_status_filter:
            order_qs = order_qs.filter(status=order_status_filter)
        if from_date:
            voucher_qs = voucher_qs.filter(created_at__date__gte=from_date)
            order_qs = order_qs.filter(created_at__date__gte=from_date)
        if to_date:
            voucher_qs = voucher_qs.filter(created_at__date__lte=to_date)
            order_qs = order_qs.filter(created_at__date__lte=to_date)

        service_summary = list(
            voucher_qs.values('service_code')
            .annotate(
                txn_count=Count('id'),
                credit_total=Coalesce(
                    Sum(
                        Case(
                            When(transaction_type=ParkPeVoucherTransaction.CREDIT, then='amount'),
                            default=Value(Decimal("0.00")),
                            output_field=DecimalField(max_digits=20, decimal_places=2),
                        )
                    ),
                    Value(Decimal("0.00")),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                ),
                debit_total=Coalesce(
                    Sum(
                        Case(
                            When(transaction_type=ParkPeVoucherTransaction.DEBIT, then='amount'),
                            default=Value(Decimal("0.00")),
                            output_field=DecimalField(max_digits=20, decimal_places=2),
                        )
                    ),
                    Value(Decimal("0.00")),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                ),
            )
            .order_by('service_code')
        )

        order_summary = list(
            order_qs.values('gateway', 'status')
            .annotate(
                order_count=Count('id'),
                total_amount=Coalesce(
                    Sum('amount'),
                    Value(Decimal("0.00")),
                    output_field=DecimalField(max_digits=20, decimal_places=2),
                ),
            )
            .order_by('gateway', 'status')
        )

        ledger_totals = voucher_qs.aggregate(
            credit_total=Coalesce(
                Sum(
                    Case(
                        When(transaction_type=ParkPeVoucherTransaction.CREDIT, then='amount'),
                        default=Value(Decimal("0.00")),
                        output_field=DecimalField(max_digits=20, decimal_places=2),
                    )
                ),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=20, decimal_places=2),
            ),
            debit_total=Coalesce(
                Sum(
                    Case(
                        When(transaction_type=ParkPeVoucherTransaction.DEBIT, then='amount'),
                        default=Value(Decimal("0.00")),
                        output_field=DecimalField(max_digits=20, decimal_places=2),
                    )
                ),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=20, decimal_places=2),
            ),
            txn_count=Count('id'),
        )

        recent_voucher_txns = [
            {
                'source': 'voucher_ledger',
                'created_at': t.created_at,
                'user_id': t.user_id,
                'username': getattr(t.user, 'username', ''),
                'service_code': t.service_code or '',
                'direction': t.transaction_type,
                'amount': t.amount,
                'status': 'success',
                'reference_id': t.reference_id or '',
                'gateway': '',
                'description': t.description or '',
            }
            for t in voucher_qs.order_by('-created_at')[:50]
        ]
        recent_orders = [
            {
                'source': 'payment_order',
                'created_at': o.created_at,
                'user_id': o.user_id,
                'username': getattr(o.user, 'username', ''),
                'service_code': 'voucher_purchase',
                'direction': 'credit',
                'amount': o.amount,
                'status': o.status,
                'reference_id': o.order_id,
                'gateway': o.gateway,
                'description': 'ParkPe PG order',
            }
            for o in order_qs.order_by('-created_at')[:50]
        ]
        recent_all = sorted(recent_voucher_txns + recent_orders, key=lambda x: x['created_at'], reverse=True)[:100]

        context.update(
            {
                'service_summary': service_summary,
                'order_summary': order_summary,
                'ledger_totals': ledger_totals,
                'recent_transactions': recent_all,
                'filters': {
                    'service': service_filter,
                    'user': user_filter,
                    'order_status': order_status_filter,
                    'from': request.GET.get('from', ''),
                    'to': request.GET.get('to', ''),
                },
            }
        )
        return context
