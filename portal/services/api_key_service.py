"""
API Key service: resolve key from plain value, revoke, and optional IP check.
"""
import hashlib
from typing import Optional, Tuple

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


class APIKeyService:
    """Convenience class for admin and callers that prefer service object."""

    def find_api_key_by_plain_key(self, plain_key: str) -> Optional[Tuple[APIKey, ResellerPartner]]:
        return find_api_key_by_plain_key(plain_key)

    def revoke_api_key(self, api_key: APIKey, reason: str, revoked_by=None) -> None:
        revoke_api_key(api_key, reason, revoked_by)
