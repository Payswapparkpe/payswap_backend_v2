"""
VoucherX Service - Statistics and analytics for VoucherX dashboard
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Count, Q, Avg, F
from portal.models import (
    GiftVoucherBrand, GiftVoucher, GiftVoucherTransaction,
    BulkVoucherIssuanceBatch
)
from portal.utils.logging_helper import get_logger

logger = get_logger('portal.services.voucherx')


class VoucherXService:
    """Service for VoucherX statistics and analytics"""
    
    def __init__(self):
        pass
    
    def get_dashboard_stats(self, user) -> Dict[str, Any]:
        """
        Get comprehensive dashboard statistics
        
        Args:
            user: Current user (for permission-based filtering)
            
        Returns:
            Dictionary with all dashboard statistics
        """
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)
        month_start = today_start - timedelta(days=30)
        
        # Brand Statistics
        total_brands = GiftVoucherBrand.objects.count()
        active_brands = GiftVoucherBrand.objects.filter(status='ACTIVE').count()
        onboarded_brands = GiftVoucherBrand.objects.filter(
            onboarding_status='APPROVED',
            status='ACTIVE'
        ).count()
        pending_onboarding = GiftVoucherBrand.objects.filter(
            onboarding_status='SUBMITTED'
        ).count()
        in_progress_onboarding = GiftVoucherBrand.objects.filter(
            onboarding_status='IN_PROGRESS'
        ).count()
        
        # Voucher Statistics
        total_vouchers = GiftVoucher.objects.count()
        active_vouchers = GiftVoucher.objects.filter(status='ACTIVE').count()
        redeemed_vouchers = GiftVoucher.objects.filter(
            status__in=['REDEEMED', 'PARTIALLY_REDEEMED']
        ).count()
        
        # Issuance Statistics
        vouchers_today = GiftVoucher.objects.filter(
            issued_at__gte=today_start
        ).count()
        vouchers_week = GiftVoucher.objects.filter(
            issued_at__gte=week_start
        ).count()
        vouchers_month = GiftVoucher.objects.filter(
            issued_at__gte=month_start
        ).count()
        
        # Value Statistics
        total_value = GiftVoucher.objects.aggregate(
            total=Sum('original_amount')
        )['total'] or Decimal('0.00')
        
        outstanding_balance = GiftVoucher.objects.filter(
            status__in=['ACTIVE', 'PARTIALLY_REDEEMED']
        ).aggregate(
            total=Sum('current_balance')
        )['total'] or Decimal('0.00')
        
        redeemed_value = GiftVoucherTransaction.objects.filter(
            transaction_type='REDEMPTION',
            transaction_status='SUCCESS'
        ).aggregate(
            total=Sum('transaction_amount')
        )['total'] or Decimal('0.00')
        
        # Today's value
        today_value = GiftVoucher.objects.filter(
            issued_at__gte=today_start
        ).aggregate(
            total=Sum('original_amount')
        )['total'] or Decimal('0.00')
        
        # Week's value
        week_value = GiftVoucher.objects.filter(
            issued_at__gte=week_start
        ).aggregate(
            total=Sum('original_amount')
        )['total'] or Decimal('0.00')
        
        # Month's value
        month_value = GiftVoucher.objects.filter(
            issued_at__gte=month_start
        ).aggregate(
            total=Sum('original_amount')
        )['total'] or Decimal('0.00')
        
        # Bulk Issuance Statistics
        total_batches = BulkVoucherIssuanceBatch.objects.count()
        active_batches = BulkVoucherIssuanceBatch.objects.filter(
            status='PROCESSING'
        ).count()
        completed_batches = BulkVoucherIssuanceBatch.objects.filter(
            status='COMPLETED'
        ).count()
        
        return {
            'brands': {
                'total': total_brands,
                'active': active_brands,
                'onboarded': onboarded_brands,
                'pending_onboarding': pending_onboarding,
                'in_progress_onboarding': in_progress_onboarding,
            },
            'vouchers': {
                'total': total_vouchers,
                'active': active_vouchers,
                'redeemed': redeemed_vouchers,
                'today': vouchers_today,
                'week': vouchers_week,
                'month': vouchers_month,
            },
            'value': {
                'total_issued': float(total_value),
                'outstanding': float(outstanding_balance),
                'redeemed': float(redeemed_value),
                'today': float(today_value),
                'week': float(week_value),
                'month': float(month_value),
            },
            'bulk_issuance': {
                'total_batches': total_batches,
                'active_batches': active_batches,
                'completed_batches': completed_batches,
            }
        }
    
    def get_recent_activity(self, user, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent voucher-related activities
        
        Args:
            user: Current user
            limit: Maximum number of activities to return
            
        Returns:
            List of activity dictionaries
        """
        activities = []
        
        # Recent voucher issuances
        recent_vouchers = GiftVoucher.objects.select_related(
            'brand', 'created_by'
        ).order_by('-issued_at')[:limit]
        
        for voucher in recent_vouchers:
            activities.append({
                'type': 'voucher_issued',
                'timestamp': voucher.issued_at,
                'title': f'Voucher {voucher.voucher_code} issued',
                'description': f'Brand: {voucher.brand.brand_name}, Amount: ₹{voucher.original_amount}',
                'user': voucher.created_by.username if voucher.created_by else 'System',
                'icon': 'gift',
                'color': 'green',
            })
        
        # Recent brand onboarding submissions
        recent_submissions = GiftVoucherBrand.objects.filter(
            onboarding_status='SUBMITTED'
        ).select_related('created_by').order_by('-updated_at')[:5]
        
        for brand in recent_submissions:
            activities.append({
                'type': 'brand_submitted',
                'timestamp': brand.updated_at,
                'title': f'{brand.brand_name} submitted for review',
                'description': f'Brand code: {brand.brand_code}',
                'user': brand.created_by.username if brand.created_by else 'Unknown',
                'icon': 'checklist',
                'color': 'blue',
            })
        
        # Recent approvals
        recent_approvals = GiftVoucherBrand.objects.filter(
            onboarding_status='APPROVED',
            onboarding_completed_at__isnull=False
        ).select_related('onboarding_approved_by').order_by('-onboarding_completed_at')[:5]
        
        for brand in recent_approvals:
            activities.append({
                'type': 'brand_approved',
                'timestamp': brand.onboarding_completed_at,
                'title': f'{brand.brand_name} approved',
                'description': f'Approved by: {brand.onboarding_approved_by.username if brand.onboarding_approved_by else "Admin"}',
                'user': brand.onboarding_approved_by.username if brand.onboarding_approved_by else 'Admin',
                'icon': 'check-circle',
                'color': 'green',
            })
        
        # Sort by timestamp and return top N
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        return activities[:limit]
    
    def get_pending_tasks(self, user) -> Dict[str, Any]:
        """
        Get pending tasks for the user
        
        Args:
            user: Current user
            
        Returns:
            Dictionary with pending tasks
        """
        # Only admins and super users see onboarding reviews
        pending_onboarding_reviews = 0
        if user.role_code in ['admin', 'super'] or user.is_staff:
            pending_onboarding_reviews = GiftVoucherBrand.objects.filter(
                onboarding_status='SUBMITTED'
            ).count()
        
        # Active bulk issuance batches
        active_batches = BulkVoucherIssuanceBatch.objects.filter(
            status='PROCESSING',
            created_by=user
        ).count()
        
        return {
            'onboarding_reviews': pending_onboarding_reviews,
            'active_batches': active_batches,
            'total': pending_onboarding_reviews + active_batches,
        }
    
    def get_brand_summary(self) -> Dict[str, Any]:
        """
        Get brand summary statistics
        
        Returns:
            Dictionary with brand statistics
        """
        brands = GiftVoucherBrand.objects.all()
        
        by_status = {}
        for status_code, status_label in GiftVoucherBrand.STATUS_CHOICES:
            by_status[status_code] = brands.filter(status=status_code).count()
        
        by_onboarding = {}
        for onboarding_code, onboarding_label in GiftVoucherBrand.ONBOARDING_STATUS_CHOICES:
            by_onboarding[onboarding_code] = brands.filter(
                onboarding_status=onboarding_code
            ).count()
        
        return {
            'by_status': by_status,
            'by_onboarding': by_onboarding,
        }
    
    def get_issuance_summary(self, date_range: Optional[str] = None) -> Dict[str, Any]:
        """
        Get voucher issuance summary
        
        Args:
            date_range: Optional date range ('today', 'week', 'month', 'all')
            
        Returns:
            Dictionary with issuance statistics
        """
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if date_range == 'today':
            start_date = today_start
        elif date_range == 'week':
            start_date = today_start - timedelta(days=7)
        elif date_range == 'month':
            start_date = today_start - timedelta(days=30)
        else:
            start_date = None
        
        queryset = GiftVoucher.objects.all()
        if start_date:
            queryset = queryset.filter(issued_at__gte=start_date)
        
        total_issued = queryset.count()
        total_value = queryset.aggregate(
            total=Sum('original_amount')
        )['total'] or Decimal('0.00')
        
        avg_value = queryset.aggregate(
            avg=Avg('original_amount')
        )['avg'] or Decimal('0.00')
        
        # By brand
        by_brand = queryset.values('brand__brand_name').annotate(
            count=Count('id'),
            total_value=Sum('original_amount')
        ).order_by('-count')[:10]
        
        return {
            'total_issued': total_issued,
            'total_value': float(total_value),
            'avg_value': float(avg_value),
            'by_brand': list(by_brand),
        }
