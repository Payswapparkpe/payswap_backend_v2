"""
View Mixins
Reusable mixins for views to eliminate duplicate code
"""
from django.db.models import Q
from typing import Optional


class IssuerTypeMixin:
    """Mixin to determine issuer type for voucher operations"""
    
    def get_issuer_type(self, user):
        """
        Determine issuer type based on user role and context
        
        Args:
            user: User object
            
        Returns:
            Issuer type string: 'ADMIN', 'API_PARTNER', or 'BRAND_OWNER'
        """
        if not user or not hasattr(user, 'role_code'):
            return 'ADMIN'  # Default fallback
        
        role_code = user.role_code
        
        # Admin users
        if role_code == 'ADMIN' or user.is_staff or user.is_superuser:
            return 'ADMIN'
        
        # Check if user is a reseller/API partner
        if hasattr(user, 'reseller_partner') and user.reseller_partner:
            return 'API_PARTNER'
        
        # Check if user is associated with a brand
        if hasattr(user, 'brand_associations'):
            # If user is associated with brand(s), they're a brand owner
            if user.brand_associations.exists():
                return 'BRAND_OWNER'
        
        # Default to ADMIN for other roles
        return 'ADMIN'
    
    def get_issuer_name(self, user) -> str:
        """
        Get issuer name for display
        
        Args:
            user: User object
            
        Returns:
            Issuer name string
        """
        from portal.utils.user_utils_enhanced import get_issuer_name
        return get_issuer_name(user)


class ReportQueryMixin:
    """Mixin for building report queries with common filters"""
    
    def build_report_query(
        self,
        queryset,
        brand_id: Optional[int] = None,
        client_id: Optional[int] = None,
        issuer_type: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        search: Optional[str] = None
    ):
        """
        Build filtered queryset for reports
        
        Args:
            queryset: Base queryset
            brand_id: Filter by brand ID
            client_id: Filter by client ID
            issuer_type: Filter by issuer type
            status: Filter by status
            date_from: Start date filter
            date_to: End date filter
            search: Search term
            
        Returns:
            Filtered queryset
        """
        # Brand filter
        if brand_id:
            queryset = queryset.filter(brand_id=brand_id)
        
        # Client filter
        if client_id:
            queryset = queryset.filter(client_id=client_id)
        
        # Issuer type filter
        if issuer_type:
            queryset = queryset.filter(issuer_type=issuer_type)
        
        # Status filter
        if status:
            queryset = queryset.filter(status=status)
        
        # Date range filters
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Search filter (customize based on model)
        if search:
            queryset = self.apply_search_filter(queryset, search)
        
        return queryset
    
    def apply_search_filter(self, queryset, search_term: str):
        """
        Apply search filter to queryset
        Override this method in views for model-specific search
        
        Args:
            queryset: Queryset to filter
            search_term: Search term
            
        Returns:
            Filtered queryset
        """
        # Default implementation - searches common fields
        # Override in specific views for custom search logic
        return queryset.filter(
            Q(id__icontains=search_term) |
            Q(code__icontains=search_term) |
            Q(name__icontains=search_term)
        )
    
    def get_date_range_filters(self, request):
        """
        Extract date range filters from request
        
        Args:
            request: Django request object
            
        Returns:
            Dictionary with date_from and date_to
        """
        date_from = request.GET.get('date_from') or request.POST.get('date_from')
        date_to = request.GET.get('date_to') or request.POST.get('date_to')
        
        return {
            'date_from': date_from,
            'date_to': date_to
        }
    
    def get_pagination_params(self, request, default_page_size: int = 20):
        """
        Extract pagination parameters from request
        
        Args:
            request: Django request object
            default_page_size: Default page size if not specified
            
        Returns:
            Dictionary with page and page_size
        """
        try:
            page = int(request.GET.get('page', 1))
            page = max(1, page)  # Ensure page is at least 1
        except (TypeError, ValueError):
            page = 1
        
        try:
            page_size = int(request.GET.get('page_size', default_page_size))
            page_size = min(max(1, page_size), 100)  # Clamp between 1 and 100
        except (TypeError, ValueError):
            page_size = default_page_size
        
        return {
            'page': page,
            'page_size': page_size
        }
