"""
Secure Logging Helper
Provides clean, secure logging utilities with sensitive data sanitization
"""
import logging
import json
import re
from typing import Any, Dict, Optional, List
from datetime import datetime
from django.conf import settings

# Sensitive fields to mask in logs
SENSITIVE_FIELDS = [
    'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 'api_secret',
    'access_token', 'refresh_token', 'authorization', 'auth', 'credential',
    'private_key', 'privatekey', 'seed_phrase', 'totp_secret', 'encrypted',
    'ssn', 'pan', 'aadhaar', 'credit_card', 'card_number', 'cvv', 'pin',
    'otp', 'verification_code', 'mfa_code'
]

# Patterns for sensitive data detection
SENSITIVE_PATTERNS = [
    r'password["\']?\s*[:=]\s*["\']?([^"\']+)',
    r'token["\']?\s*[:=]\s*["\']?([^"\']+)',
    r'api[_-]?key["\']?\s*[:=]\s*["\']?([^"\']+)',
    r'secret["\']?\s*[:=]\s*["\']?([^"\']+)',
    r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',  # Credit card pattern
    r'\b\d{12}\b',  # Aadhaar pattern
    r'\b[A-Z]{5}\d{4}[A-Z]\b',  # PAN pattern
]


class SecureLogger:
    """
    Secure logging utility with automatic sensitive data sanitization
    """
    
    def __init__(self, name: str = 'portal', log_level: str = 'INFO'):
        self.logger = logging.getLogger(name)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger.setLevel(self.log_level)
    
    def _sanitize_value(self, value: Any) -> Any:
        """
        Sanitize a single value by masking sensitive data
        
        Args:
            value: Value to sanitize
        
        Returns:
            Sanitized value
        """
        if value is None:
            return None
        
        # If it's a string, check for sensitive patterns
        if isinstance(value, str):
            # Mask if it looks like a password/token (length > 8, alphanumeric)
            if len(value) > 8 and value.isalnum():
                # Check if it matches sensitive patterns
                for pattern in SENSITIVE_PATTERNS:
                    if re.search(pattern, value, re.IGNORECASE):
                        return '***REDACTED***'
            
            # Mask if it's a long string (likely token/secret)
            if len(value) > 20:
                # Check against known sensitive field names in context
                return value[:4] + '***REDACTED***' + value[-4:] if len(value) > 8 else '***REDACTED***'
        
        return value
    
    def _sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively sanitize dictionary, masking sensitive fields
        
        Args:
            data: Dictionary to sanitize
        
        Returns:
            Sanitized dictionary
        """
        if not isinstance(data, dict):
            return data
        
        sanitized = {}
        for key, value in data.items():
            # Check if key is sensitive
            key_lower = key.lower()
            is_sensitive = any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS)
            
            if is_sensitive:
                # Mask sensitive fields
                if isinstance(value, str):
                    sanitized[key] = '***REDACTED***'
                elif isinstance(value, (dict, list)):
                    sanitized[key] = '***REDACTED***'
                else:
                    sanitized[key] = '***REDACTED***'
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                sanitized[key] = [self._sanitize_dict(item) if isinstance(item, dict) else self._sanitize_value(item) for item in value]
            else:
                sanitized[key] = self._sanitize_value(value)
        
        return sanitized
    
    def _sanitize_message(self, message: str) -> str:
        """
        Sanitize log message string
        
        Args:
            message: Log message
        
        Returns:
            Sanitized message
        """
        if not isinstance(message, str):
            return str(message)
        
        # Replace sensitive patterns (simplified to avoid regex group issues)
        sanitized = message
        # Simple replacement for common patterns
        sensitive_words = ['password', 'token', 'secret', 'api_key', 'api_secret']
        for word in sensitive_words:
            # Replace word=value patterns
            pattern = rf'{word}\s*[:=]\s*["\']?([^"\'\s]+)'
            sanitized = re.sub(pattern, f'{word}=***REDACTED***', sanitized, flags=re.IGNORECASE)
        
        return sanitized
    
    def _format_log_data(
        self,
        level: str,
        message: str,
        user: Optional[Any] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        traceback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format log data structure
        
        Args:
            level: Log level
            message: Log message
            user: User instance (optional)
            extra_data: Additional data (optional)
            request_id: Request ID for tracing (optional)
            traceback: Traceback string (optional)
        
        Returns:
            Formatted log dictionary
        """
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level.upper(),
            'message': self._sanitize_message(message),
            'service': 'portal',
        }
        
        # Add user information (sanitized)
        if user:
            log_data['user'] = {
                'id': user.id,
                'username': user.username,
                'role': user.role_code if hasattr(user, 'role_code') else None,
            }
        
        # Add request ID for tracing
        if request_id:
            log_data['request_id'] = request_id
        
        # Add extra data (sanitized)
        if extra_data:
            log_data['data'] = self._sanitize_dict(extra_data)
        
        # Add traceback if error
        if traceback:
            log_data['traceback'] = traceback
        
        return log_data
    
    def _write_log(
        self,
        level: str,
        message: str,
        user: Optional[Any] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        traceback: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        url: Optional[str] = None
    ):
        """
        Write log entry via write_logs_task (ONLY way to write logs)
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            user: User instance (optional)
            extra_data: Additional data (optional)
            request_id: Request ID for tracing (optional)
            traceback: Traceback string (optional)
            client_ip: Client IP address (optional)
            user_agent: User agent (optional)
            session_id: Session ID (optional)
            url: URL path (optional)
        """
        from portal.tasks.write_logs_task import write_logs_task
        from portal.utils.logging_utils import get_module_name
        
        # Get module name from caller
        module_name = get_module_name(skip_frames=3)
        
        # Extract user ID
        user_id = user.id if user else None
        
        # Call write_logs_task (async)
        write_logs_task.delay(
            log_level=level,
            message=message,
            module_name=module_name,
            url=url,
            request_id=request_id,
            response_id=None,  # Not available in non-API contexts
            user_id=user_id,
            extra_data=extra_data,
            client_ip=client_ip,
            user_agent=user_agent,
            session_id=session_id
        )
    
    def debug(
        self,
        message: str,
        user: Optional[Any] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        url: Optional[str] = None
    ):
        """Log debug message"""
        self._write_log('DEBUG', message, user, extra_data, request_id, None, client_ip, user_agent, session_id, url)
    
    def info(
        self,
        message: str,
        user: Optional[Any] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        url: Optional[str] = None
    ):
        """Log info message"""
        self._write_log('INFO', message, user, extra_data, request_id, None, client_ip, user_agent, session_id, url)
    
    def warning(
        self,
        message: str,
        user: Optional[Any] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        url: Optional[str] = None
    ):
        """Log warning message"""
        self._write_log('WARNING', message, user, extra_data, request_id, None, client_ip, user_agent, session_id, url)
    
    def error(
        self,
        message: str,
        user: Optional[Any] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        traceback: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        url: Optional[str] = None
    ):
        """Log error message"""
        self._write_log('ERROR', message, user, extra_data, request_id, traceback, client_ip, user_agent, session_id, url)
    
    def critical(
        self,
        message: str,
        user: Optional[Any] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        traceback: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        url: Optional[str] = None
    ):
        """Log critical message"""
        self._write_log('CRITICAL', message, user, extra_data, request_id, traceback, client_ip, user_agent, session_id, url)
    
    def log_user_action(
        self,
        action: str,
        user: Any,
        resource: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: str = 'success',
        extra_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        url: Optional[str] = None
    ):
        """
        Log user action with structured data
        
        Args:
            action: Action performed (e.g., 'login', 'create_user', 'update_profile')
            user: User performing the action
            resource: Resource type (e.g., 'user', 'profile', 'wallet')
            resource_id: Resource ID
            status: Action status ('success', 'failed', 'pending')
            extra_data: Additional data
            request_id: Request ID for tracing
            client_ip: Client IP address
            user_agent: User agent
            session_id: Session ID
            url: URL path
        """
        action_data = {
            'action': action,
            'resource': resource,
            'resource_id': resource_id,
            'status': status,
        }
        
        if extra_data:
            action_data.update(extra_data)
        
        level = 'INFO' if status == 'success' else 'WARNING'
        message = f"User action: {action}"
        if resource:
            message += f" on {resource}"
        if resource_id:
            message += f" (ID: {resource_id})"
        message += f" - {status}"
        
        self._write_log(level, message, user, action_data, request_id, None, client_ip, user_agent, session_id, url)
    
    def log_api_call(
        self,
        service: str,
        endpoint: str,
        method: str = 'POST',
        status_code: Optional[int] = None,
        response_time: Optional[float] = None,
        user: Optional[Any] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        url: Optional[str] = None
    ):
        """
        Log API call with structured data
        
        Args:
            service: Service name (e.g., 'kaleyra', 'cashfree', 'aws_s3')
            endpoint: API endpoint
            method: HTTP method
            status_code: Response status code
            response_time: Response time in seconds
            user: User making the call (optional)
            extra_data: Additional data
            request_id: Request ID for tracing
            client_ip: Client IP address
            user_agent: User agent
            session_id: Session ID
            url: URL path
        """
        api_data = {
            'service': service,
            'endpoint': endpoint,
            'method': method,
            'status_code': status_code,
            'response_time_ms': response_time * 1000 if response_time else None,
        }
        
        if extra_data:
            api_data.update(extra_data)
        
        level = 'INFO' if status_code and 200 <= status_code < 400 else 'WARNING'
        message = f"API call: {method} {service}/{endpoint}"
        if status_code:
            message += f" - {status_code}"
        if response_time:
            message += f" ({response_time:.2f}s)"
        
        self._write_log(level, message, user, api_data, request_id, None, client_ip, user_agent, session_id, url)
    
    def log_security_event(
        self,
        event_type: str,
        message: str,
        user: Optional[Any] = None,
        severity: str = 'medium',
        extra_data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        url: Optional[str] = None
    ):
        """
        Log security event
        
        Args:
            event_type: Event type (e.g., 'failed_login', 'mfa_bypass_attempt', 'unauthorized_access')
            message: Event message
            user: User involved (optional)
            severity: Severity level ('low', 'medium', 'high', 'critical')
            extra_data: Additional data
            request_id: Request ID for tracing
            client_ip: Client IP address
            user_agent: User agent
            session_id: Session ID
            url: URL path
        """
        security_data = {
            'event_type': event_type,
            'severity': severity,
        }
        
        if extra_data:
            security_data.update(extra_data)
        
        level_map = {
            'low': 'INFO',
            'medium': 'WARNING',
            'high': 'ERROR',
            'critical': 'CRITICAL'
        }
        level = level_map.get(severity, 'WARNING')
        
        self._write_log(level, f"Security event: {message}", user, security_data, request_id, None, client_ip, user_agent, session_id, url)


# Global logger instance
secure_logger = SecureLogger('portal')


def sanitize_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize sensitive data in dictionary for logging
    
    Args:
        data: Dictionary to sanitize
    
    Returns:
        Sanitized dictionary
    """
    logger = SecureLogger()
    return logger._sanitize_dict(data)


def get_logger(name: str = 'portal') -> SecureLogger:
    """
    Get a secure logger instance
    
    Args:
        name: Logger name
    
    Returns:
        SecureLogger instance
    """
    return SecureLogger(name)
