"""
API Version 1 Authentication - Internal Access
"""
from rest_framework.authentication import SessionAuthentication, TokenAuthentication


class InternalAuthentication(SessionAuthentication, TokenAuthentication):
    """
    Combined authentication for internal API
    Supports both session and token authentication
    """
    pass
