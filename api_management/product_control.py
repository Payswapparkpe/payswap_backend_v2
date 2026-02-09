"""
Product-level API control (Parkpe / Payswap).
When a product is disabled, all APIs under that product are blocked for that platform.
"""
from typing import Optional

from .models import APIProduct


def get_platform_from_request(request) -> Optional[str]:
    """
    Get platform from request: header X-App, or query param app.
    Returns 'parkpe', 'payswap', or None (meaning check both / backward compatible).
    """
    app = (
        request.META.get("HTTP_X_APP")
        or request.GET.get("app")
        or (getattr(request, "data", None) and request.data.get("app") if hasattr(request, "data") else None)
    )
    if not app:
        return None
    app = str(app).strip().lower()
    if app in ("parkpe", "payswap"):
        return app
    return None


def is_product_enabled(platform: Optional[str], product_slug: str, request=None) -> bool:
    """
    Check if the product is enabled for the given platform.
    - If platform is None and request is given, derive platform from request; if still None, allow (any platform enabled).
    - If platform is None and no request, allow (backward compatible).
    """
    if request is not None and platform is None:
        platform = get_platform_from_request(request)

    if not platform:
        # No platform: allow if at least one platform has this product enabled
        return APIProduct.objects.filter(product_slug=product_slug, enabled=True).exists()

    try:
        product = APIProduct.objects.get(platform=platform, product_slug=product_slug)
        return product.enabled
    except APIProduct.DoesNotExist:
        # Product not configured for this platform: allow (admin may not have added it yet)
        return True
