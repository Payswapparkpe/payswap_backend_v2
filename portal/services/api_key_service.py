"""
API Key service: resolve key from plain value, revoke, create, and optional IP check.
"""
import hashlib
import secrets
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone

from portal.models import APIKey, ResellerPartner


def _hash_key(plain_key: str) -> str:
    return hashlib.sha256(plain_key.encode()).hexdigest()


def find_api_key_by_plain_key(plain_key: str) -> Optional[Tuple[APIKey, ResellerPartner]]:
    """
    Look up APIKey by plain key (hashed and compared). Returns (APIKey, Partner) or None.
    Caller should also check is_active() and is_ip_allowed(client_ip).
    """
    if not plain_key or not plain_key.strip():
        return None
    key_hash = _hash_key(plain_key.strip())
    try:
        api_key = APIKey.objects.select_related("partner").get(api_key=key_hash)
        return (api_key, api_key.partner)
    except APIKey.DoesNotExist:
        return None


def revoke_api_key(api_key: APIKey, reason: str, revoked_by=None) -> None:
    """Revoke an API key and set revoked_at and revoked_reason."""
    api_key.status = APIKey.STATUS_CHOICES[1][0]  # 'REVOKED'
    api_key.revoked_at = timezone.now()
    api_key.revoked_reason = reason or "Revoked by admin"
    api_key.save(update_fields=["status", "revoked_at", "revoked_reason", "updated_at"])


def create_api_key(
    partner: ResellerPartner,
    key_name: str,
    key_type: str = "LIVE",
    permissions: Optional[Dict[str, Any]] = None,
    rate_limits: Optional[Dict[str, Any]] = None,
    rate_limit: Optional[Dict[str, Any]] = None,
    ip_whitelist: Optional[List[str]] = None,
    created_by=None,
) -> Tuple[APIKey, str, str]:
    """
    Create a new API key for a partner. Returns (APIKey, plain_key, plain_secret).
    Plain key/secret are shown only once; store hashed in DB.
    """
    plain_key = secrets.token_urlsafe(32)
    plain_secret = secrets.token_urlsafe(32)
    key_prefix = f"psk_{key_type.lower()}_{plain_key[:8]}"
    api_key_obj = APIKey(
        partner=partner,
        key_name=key_name,
        api_key=_hash_key(plain_key),
        api_secret=_hash_key(plain_secret),
        key_prefix=key_prefix[:20],
        key_type=key_type,
        status="ACTIVE",
        permissions=permissions or {},
        rate_limit=rate_limits if rate_limits is not None else (rate_limit or {}),
        ip_whitelist=ip_whitelist or [],
        created_by=created_by,
    )
    api_key_obj.save()
    return (api_key_obj, plain_key, plain_secret)


class APIKeyService:
    """Convenience class for admin and callers that prefer service object."""

    def find_api_key_by_plain_key(self, plain_key: str) -> Optional[Tuple[APIKey, ResellerPartner]]:
        return find_api_key_by_plain_key(plain_key)

    def revoke_api_key(self, api_key: APIKey, reason: str, revoked_by=None) -> None:
        revoke_api_key(api_key, reason, revoked_by)

    @classmethod
    def create_api_key(
        cls,
        partner: ResellerPartner,
        key_name: str,
        key_type: str = "LIVE",
        permissions: Optional[Dict[str, Any]] = None,
        rate_limits: Optional[Dict[str, Any]] = None,
        rate_limit: Optional[Dict[str, Any]] = None,
        ip_whitelist: Optional[List[str]] = None,
        created_by=None,
    ) -> Tuple[APIKey, str, str]:
        """Create a new API key. Returns (APIKey, plain_key, plain_secret)."""
        return create_api_key(
            partner=partner,
            key_name=key_name,
            key_type=key_type,
            permissions=permissions,
            rate_limits=rate_limits,
            rate_limit=rate_limit,
            ip_whitelist=ip_whitelist,
            created_by=created_by,
        )
