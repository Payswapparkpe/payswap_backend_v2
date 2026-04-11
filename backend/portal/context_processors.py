"""
Context processors for portal app
"""
from portal.models import GiftVoucherBrand


def voucherx_context(request):
    """Add VoucherX-related context variables to all templates"""
    context = {}
    
    # Only calculate for authenticated users who can see it
    if request.user.is_authenticated:
        if request.user.role_code in ['admin', 'super'] or request.user.is_staff:
            context['brand_onboarding_pending_count'] = GiftVoucherBrand.objects.filter(
                onboarding_status='SUBMITTED'
            ).count()
        else:
            context['brand_onboarding_pending_count'] = 0
    else:
        context['brand_onboarding_pending_count'] = 0
    
    return context
