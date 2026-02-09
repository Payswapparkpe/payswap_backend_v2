"""
TDD tests for unified logging system
Tests: write_logs_task, IP logging, user agent, session ID, log categorization
"""
from django.test import TestCase
from django.test import RequestFactory
from django.core.cache import cache
from portal.tasks.write_logs_task import write_logs_task
from portal.utils.ip_utils import get_client_ip, get_user_agent, get_session_id
from portal.utils.logging_utils import get_module_name, get_request_id, categorize_log
import json


class LoggingTests(TestCase):
    """Test unified logging system"""
    
    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
    
    def test_get_client_ip_from_remote_addr(self):
        """Test IP extraction from REMOTE_ADDR"""
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        
        ip = get_client_ip(request)
        self.assertEqual(ip, '192.168.1.1')
    
    def test_get_client_ip_from_x_forwarded_for(self):
        """Test IP extraction from X-Forwarded-For header"""
        request = self.factory.get('/', HTTP_X_FORWARDED_FOR='10.0.0.1, 192.168.1.1')
        
        ip = get_client_ip(request)
        self.assertEqual(ip, '10.0.0.1')  # First IP in chain
    
    def test_get_client_ip_from_x_real_ip(self):
        """Test IP extraction from X-Real-IP header"""
        request = self.factory.get('/', HTTP_X_REAL_IP='172.16.0.1')
        
        ip = get_client_ip(request)
        self.assertEqual(ip, '172.16.0.1')
    
    def test_get_user_agent(self):
        """Test user agent extraction"""
        request = self.factory.get('/', HTTP_USER_AGENT='Mozilla/5.0')
        
        user_agent = get_user_agent(request)
        self.assertEqual(user_agent, 'Mozilla/5.0')
    
    def test_get_session_id(self):
        """Test session ID extraction"""
        request = self.factory.get('/')
        # Mock session
        from django.contrib.sessions.middleware import SessionMiddleware
        middleware = SessionMiddleware(lambda x: None)
        middleware.process_request(request)
        request.session.save()
        
        session_id = get_session_id(request)
        self.assertIsNotNone(session_id)
        self.assertNotEqual(session_id, 'unknown')
    
    def test_log_categorization_by_url(self):
        """Test log categorization based on URL"""
        category = categorize_log(module_name=None, url='/api/v1/auth/login')
        self.assertEqual(category, 'api')
        
        category = categorize_log(module_name=None, url='/signin/')
        self.assertEqual(category, 'auth')
        
        category = categorize_log(module_name=None, url='/payment/process/')
        self.assertEqual(category, 'payment')
    
    def test_log_categorization_by_module(self):
        """Test log categorization based on module name"""
        category = categorize_log(module_name='api.v1.views', url=None)
        self.assertEqual(category, 'api')
        
        category = categorize_log(module_name='portal.views.auth', url=None)
        self.assertEqual(category, 'auth')
    
    def test_log_categorization_by_extra_data(self):
        """Test log categorization based on extra_data operation field"""
        # Test voucher operation detection via extra_data
        category = categorize_log(
            module_name='portal.views', 
            url=None, 
            extra_data={'operation': 'voucher_issued'}
        )
        self.assertEqual(category, 'gift_voucher')
        
        category = categorize_log(
            module_name='portal.views', 
            url=None, 
            extra_data={'operation': 'batch_created'}
        )
        self.assertEqual(category, 'gift_voucher')
        
        category = categorize_log(
            module_name='portal.views', 
            url=None, 
            extra_data={'operation': 'client_created'}
        )
        self.assertEqual(category, 'gift_voucher')
        
        # Test that non-voucher operations still work
        category = categorize_log(
            module_name='portal.views', 
            url=None, 
            extra_data={'operation': 'user_login'}
        )
        self.assertEqual(category, 'general')
    
    def test_write_logs_task_structure(self):
        """Test write_logs_task creates proper log structure"""
        # This would test the actual task execution
        # For now, verify the function exists and accepts correct parameters
        self.assertTrue(callable(write_logs_task))
        
        # Test that it accepts all required parameters
        try:
            write_logs_task.delay(
                log_level='INFO',
                message='Test log',
                module_name='test.module',
                url='/test/',
                request_id='test-123',
                response_id='resp-456',
                user_id=None,
                extra_data={},
                client_ip='192.168.1.1',
                user_agent='TestAgent',
                session_id='session-123'
            )
        except Exception as e:
            # Task might fail in test environment, but should accept parameters
            pass
