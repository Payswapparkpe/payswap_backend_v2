"""
API Version 2 Serializers - External Parties
"""
from rest_framework import serializers


class BaseExternalSerializer(serializers.Serializer):
    """
    Base serializer for external API
    """
    pass


class PublicResponseSerializer(serializers.Serializer):
    """
    Standard response serializer for public endpoints
    """
    status = serializers.CharField()
    message = serializers.CharField(required=False)
    data = serializers.DictField(required=False)
