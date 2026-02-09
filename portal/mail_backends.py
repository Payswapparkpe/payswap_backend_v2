"""
Custom email backends for Payswap.
ParkpeSMTPBackend uses certifi CA bundle so TLS to Zoho/smtppro.zoho.in works on macOS
(avoids [SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate).
"""
import logging
import ssl
from django.core.mail.backends.smtp import EmailBackend
from django.utils.functional import cached_property

logger = logging.getLogger(__name__)


def _parkpe_ssl_verify():
    from django.conf import settings
    from core.config import payswap_config
    # In DEBUG (dev), skip SSL verify so voucher email works on macOS/Zoho without .env change
    if getattr(settings, 'DEBUG', False):
        return False
    return getattr(payswap_config, 'PARKPE_SMTP_SSL_VERIFY', True)


def _parkpe_no_verify_context():
    """Context that skips cert verification (dev only when certifi/system store fails)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class ParkpeSMTPBackend(EmailBackend):
    """
    SMTP backend that uses certifi's CA bundle for TLS verification.
    Set PARKPE_SMTP_SSL_VERIFY=false in .env to disable verification (dev only) if SSL fails on macOS.
    """

    @cached_property
    def ssl_context(self):
        if not _parkpe_ssl_verify():
            return _parkpe_no_verify_context()
        try:
            import certifi
            cafile = certifi.where()
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.load_verify_locations(cafile=cafile)
            return ctx
        except Exception as e:
            logger.warning(
                "ParkpeSMTPBackend: certifi failed (%s), using unverified TLS. Set PARKPE_SMTP_SSL_VERIFY=false in .env to silence.",
                e,
            )
            return _parkpe_no_verify_context()
