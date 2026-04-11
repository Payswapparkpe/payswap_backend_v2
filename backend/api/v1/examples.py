"""
Example: How to add new endpoints using advanced patterns

This file demonstrates best practices for API v1 development.
Remove this file in production.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import BaseSerializer


# Example 1: Using ViewSet with advanced features
class ExampleViewSet(viewsets.ModelViewSet):
    """
    Example ViewSet demonstrating advanced patterns
    
    Endpoints:
    - GET /api/v1/examples/ - List all
    - POST /api/v1/examples/ - Create
    - GET /api/v1/examples/{id}/ - Retrieve
    - PUT /api/v1/examples/{id}/ - Update
    - PATCH /api/v1/examples/{id}/ - Partial update
    - DELETE /api/v1/examples/{id}/ - Delete
    - GET /api/v1/examples/{id}/custom_action/ - Custom action
    """
    # serializer_class = ExampleSerializer
    # queryset = ExampleModel.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Advanced queryset filtering"""
        queryset = super().get_queryset()
        # Add custom filtering logic here
        return queryset
    
    @action(detail=True, methods=['post'])
    def custom_action(self, request, pk=None):
        """
        Custom action endpoint
        Access via: POST /api/v1/examples/{id}/custom_action/
        """
        instance = self.get_object()
        # Your custom logic here
        return Response({'status': 'custom action executed'})
    
    @action(detail=False, methods=['get'])
    def bulk_action(self, request):
        """
        Custom list action
        Access via: GET /api/v1/examples/bulk_action/
        """
        queryset = self.get_queryset()
        # Your bulk logic here
        return Response({'count': queryset.count()})


# Example 2: Using APIView for custom endpoints
from rest_framework.views import APIView

class ExampleAPIView(APIView):
    """
    Example APIView for custom logic
    
    Access via: GET /api/v1/example/
    """
    permission_classes = []  # Public endpoint
    
    def get(self, request):
        return Response({
            'message': 'This is a custom APIView',
            'version': 'v1'
        })


# Example 3: Advanced Serializer
from rest_framework import serializers

class ExampleSerializer(BaseSerializer):
    """
    Example serializer with advanced features
    """
    name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    
    def validate_name(self, value):
        """Custom validation"""
        if len(value) < 3:
            raise serializers.ValidationError("Name must be at least 3 characters")
        return value
    
    def create(self, validated_data):
        """Custom create logic"""
        # Your custom creation logic
        return super().create(validated_data)
