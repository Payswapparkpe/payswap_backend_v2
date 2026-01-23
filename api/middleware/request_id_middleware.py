"""
Request ID Middleware
Extracts or generates request ID for all API requests
"""
import uuid
from django.utils.deprecation import MiddlewareMixin


class RequestIDMiddleware(MiddlewareMixin):
    """
    Middleware to extract or generate request ID
    Checks X-Request-ID header, generates if not present
    Attaches to request object for use in views
    """
    
    def process_request(self, request):
        """Extract or generate request ID"""
        # Check X-Request-ID header
        request_id = request.META.get('HTTP_X_REQUEST_ID')
        
        if not request_id:
            # Generate new request ID
            request_id = str(uuid.uuid4())
        
        # Attach to request object
        request.request_id = request_id
        
        # Add to response headers (will be set in process_response)
        return None
    
    def process_response(self, request, response):
        """Add request ID and response ID to response headers"""
        # Get request ID from request
        request_id = getattr(request, 'request_id', None)
        
        if request_id:
            response['X-Request-ID'] = request_id
        
        # Generate and add response ID
        import uuid
        response_id = str(uuid.uuid4())
        response['X-Response-ID'] = response_id
        
        # Store response ID in request for logging
        request.response_id = response_id
        
        return response
