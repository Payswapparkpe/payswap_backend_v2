"""
API Version 1 Serializers
"""
from rest_framework import serializers


class BaseSerializer(serializers.Serializer):
    """
    Base serializer with common fields
    """
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
