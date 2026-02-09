"""
File-based audit logging for PIN set/unlock/lockout.
NEVER log: PIN, PIN hash, OTP, or any secrets.
"""
import logging

# Uses existing portal.audit logger (file: logs/audit.log)
PIN_AUDIT_LOGGER = logging.getLogger('portal.audit')


def _safe_extra(user_id=None, action=None, client_ip=None):
    """Build extra dict for audit; no sensitive data."""
    extra = {}
    if user_id is not None:
        extra['user_id'] = user_id
    if action is not None:
        extra['action'] = action
    if client_ip is not None:
        extra['client_ip'] = client_ip
    return extra


def log_pin_set(user_id, client_ip=None):
    """Log PIN set (after successful set)."""
    PIN_AUDIT_LOGGER.info(
        'PIN set',
        extra=_safe_extra(user_id=user_id, action='pin_set', client_ip=client_ip),
    )


def log_pin_unlock_success(user_id, client_ip=None):
    """Log successful PIN unlock."""
    PIN_AUDIT_LOGGER.info(
        'PIN unlock success',
        extra=_safe_extra(user_id=user_id, action='pin_unlock_success', client_ip=client_ip),
    )


def log_pin_unlock_failure(user_id, client_ip=None):
    """Log failed PIN attempt (no PIN value)."""
    PIN_AUDIT_LOGGER.warning(
        'PIN unlock failure',
        extra=_safe_extra(user_id=user_id, action='pin_unlock_failure', client_ip=client_ip),
    )


def log_pin_lockout(user_id, client_ip=None):
    """Log PIN lockout triggered (5 failed attempts)."""
    PIN_AUDIT_LOGGER.warning(
        'PIN lockout triggered',
        extra=_safe_extra(user_id=user_id, action='pin_lockout', client_ip=client_ip),
    )


def log_forced_otp_reauth(user_id, reason, client_ip=None):
    """Log that full OTP/2FA re-authentication was required (e.g. after lockout or window expiry)."""
    PIN_AUDIT_LOGGER.info(
        'Forced OTP/2FA re-authentication: %s',
        reason,
        extra=_safe_extra(user_id=user_id, action='forced_otp_reauth', client_ip=client_ip),
    )
