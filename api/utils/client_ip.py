"""
Client IP resolution with trusted-proxy support (VAPT-002, VAPT-003).
Only trust X-Forwarded-For when REMOTE_ADDR is in TRUSTED_PROXY_IPS; otherwise use REMOTE_ADDR.
"""
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def _is_trusted_proxy(remote_addr: str) -> bool:
    """Return True if remote_addr is in the trusted proxy list (IP or CIDR)."""
    if not remote_addr:
        return False
    trusted = getattr(settings, "TRUSTED_PROXY_IPS", None) or []
    if not trusted:
        return False
    try:
        import ipaddress
        addr = ipaddress.ip_address(remote_addr.strip())
        for entry in trusted:
            entry = entry.strip()
            if not entry:
                continue
            if "/" in entry:
                try:
                    net = ipaddress.ip_network(entry, strict=False)
                    if addr in net:
                        return True
                except ValueError:
                    if entry == remote_addr:
                        return True
            else:
                try:
                    if addr == ipaddress.ip_address(entry):
                        return True
                except ValueError:
                    if entry == remote_addr:
                        return True
    except Exception as e:
        logger.warning("client_ip: could not parse REMOTE_ADDR %r: %s", remote_addr, e)
    return False


def get_client_ip(request) -> str:
    """
    Return the client IP for the request. When behind a trusted proxy (REMOTE_ADDR in
    TRUSTED_PROXY_IPS), use the leftmost value of X-Forwarded-For; otherwise use REMOTE_ADDR
    so that spoofed X-Forwarded-For is ignored.
    """
    remote_addr = request.META.get("REMOTE_ADDR") or ""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff and _is_trusted_proxy(remote_addr):
        return xff.split(",")[0].strip()
    if xff and remote_addr:
        logger.debug(
            "client_ip: X-Forwarded-For present but REMOTE_ADDR %s not in TRUSTED_PROXY_IPS; using REMOTE_ADDR",
            remote_addr,
        )
    return remote_addr or request.META.get("HTTP_X_REAL_IP") or ""
