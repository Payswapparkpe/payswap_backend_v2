"""
IP Address Utility Functions
Extract and handle client IP addresses from requests
"""
from typing import Optional
import re


def get_client_ip(request) -> str:
    """
    Extract client IP address from request
    Handles proxies, load balancers, CDNs
    
    Checks in order:
    1. X-Forwarded-For (first IP in chain)
    2. X-Real-IP
    3. REMOTE_ADDR
    
    Args:
        request: Django request object
    
    Returns:
        IP address string or 'unknown' if not found
    """
    # Check X-Forwarded-For header (most common for proxies)
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
        # Take the first one (original client)
        ip = x_forwarded_for.split(',')[0].strip()
        if is_valid_ip(ip):
            return ip
    
    # Check X-Real-IP header (nginx proxy)
    x_real_ip = request.META.get('HTTP_X_REAL_IP')
    if x_real_ip:
        ip = x_real_ip.strip()
        if is_valid_ip(ip):
            return ip
    
    # Fallback to REMOTE_ADDR
    remote_addr = request.META.get('REMOTE_ADDR')
    if remote_addr:
        ip = remote_addr.strip()
        if is_valid_ip(ip):
            return ip
    
    return 'unknown'


def get_user_agent(request) -> str:
    """
    Extract user agent from request
    
    Args:
        request: Django request object
    
    Returns:
        User agent string or 'unknown' if not found
    """
    return request.META.get('HTTP_USER_AGENT', 'unknown')


def get_session_id(request) -> str:
    """
    Get session ID from request
    
    Args:
        request: Django request object
    
    Returns:
        Session ID string or 'unknown' if not found
    """
    if hasattr(request, 'session') and request.session.session_key:
        return request.session.session_key
    return 'unknown'


def is_valid_ip(ip: str) -> bool:
    """
    Validate IP address format (IPv4 or IPv6)
    
    Args:
        ip: IP address string
    
    Returns:
        True if valid IP format, False otherwise
    """
    if not ip or ip == 'unknown':
        return False
    
    # IPv4 pattern
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    # IPv6 pattern (simplified)
    ipv6_pattern = r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|^::1$|^::$'
    
    if re.match(ipv4_pattern, ip):
        # Validate IPv4 octets (0-255)
        parts = ip.split('.')
        try:
            return all(0 <= int(part) <= 255 for part in parts)
        except ValueError:
            return False
    
    if re.match(ipv6_pattern, ip) or '::' in ip:
        return True
    
    return False


def mask_ip(ip: str) -> str:
    """
    Mask IP address for logging (privacy)
    IPv4: 192.168.1.1 -> 192.168.*.*
    IPv6: Keep first 3 groups, mask rest
    
    Args:
        ip: IP address string
    
    Returns:
        Masked IP address
    """
    if not ip or ip == 'unknown':
        return 'unknown'
    
    # IPv4 masking
    if '.' in ip:
        parts = ip.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.*.*"
    
    # IPv6 masking (keep first 3 groups)
    if ':' in ip:
        parts = ip.split(':')
        if len(parts) > 3:
            return ':'.join(parts[:3]) + ':*:*:*:*'
        return ip
    
    return ip
