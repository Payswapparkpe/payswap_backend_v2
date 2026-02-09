"""
Resolve APIRegistry for the current request (path + method).
Used by permissions, throttling, and logging.
"""
from typing import Optional

from .models import APIRegistry


def normalize_path(path: str) -> str:
    """Strip trailing slash for consistent matching."""
    return path.rstrip("/") or "/"


def get_registry_for_request(request) -> Optional[APIRegistry]:
    """
    Find APIRegistry for this request by path and method.
    Uses normalized path (strip trailing slash) and HTTP method.
    Returns None if no registry entry exists (endpoint not managed).
    """
    path = normalize_path(request.path)
    method = request.method.upper()
    # Infer version from path: /api/v1/... or /api/v2/...
    version = "v1"
    if "/api/v2/" in request.path or request.path.startswith("/api/v2"):
        version = "v2"
    elif "/api/v1/" in request.path or request.path.startswith("/api/v1"):
        version = "v1"

    try:
        return APIRegistry.objects.get(
            version=version,
            http_method=method,
            endpoint=path,
        )
    except APIRegistry.DoesNotExist:
        # Try with trailing slash on endpoint (registry might store with slash)
        try:
            return APIRegistry.objects.get(
                version=version,
                http_method=method,
                endpoint=path + "/",
            )
        except APIRegistry.DoesNotExist:
            return None
