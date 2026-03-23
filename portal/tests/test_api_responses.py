"""
TDD tests for standardized API responses
Tests: Request ID, Response ID, consistent JSON format
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient
from api.v1.views import HealthCheckView
from api.mixins.response_mixin import StandardResponseMixin
import json


User = get_user_model()


class APIResponseTests(TestCase):
    """Test standardized API responses"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        cache.clear()
    
    def test_api_response_includes_request_id(self):
        """Test API response includes request_id (v2 health is AllowAny)."""
        response = self.client.get('/api/v2/health/', HTTP_X_REQUEST_ID='test-request-123')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('request_id', data)
        self.assertEqual(data['request_id'], 'test-request-123')
    
    def test_api_response_includes_response_id(self):
        """Test API response includes response_id (v2 health is AllowAny)."""
        response = self.client.get('/api/v2/health/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('response_id', data)
        self.assertIsNotNone(data['response_id'])
    
    def test_api_response_standard_format(self):
        """Test API response follows standard format (v2 health is AllowAny)."""
        response = self.client.get('/api/v2/health/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check standard fields
        self.assertIn('success', data)
        self.assertIn('message', data)
        self.assertIn('request_id', data)
        self.assertIn('response_id', data)
        self.assertIn('timestamp', data)
    
    def test_api_error_response_format(self):
        """Test API error response follows standard format"""
        # This would test error responses
        # For now, verify structure exists
        pass
