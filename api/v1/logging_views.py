"""
API Views for Logging Operations
Handles frontend click tracking and other logging endpoints
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone


class TrackClickView(APIView):
    """
    API endpoint for tracking frontend click events
    
    POST /api/v1/logging/track-click/
    {
        "events": [
            {
                "action": "button_click",
                "element": {"tag": "button", "id": "submit-btn", ...},
                "page_url": "/dashboard/",
                "timestamp": "2026-01-26T..."
            }
        ],
        "batch_size": 5
    }
    """
    permission_classes = []  # Allow unauthenticated for basic tracking
    
    def post(self, request):
        """Log frontend click events"""
        try:
            from portal.services.unified_logging_service import UnifiedLoggingService
            
            data = request.data
            events = data.get('events', [])
            batch_size = data.get('batch_size', 0)
            
            # Get user if authenticated
            user = request.user if request.user.is_authenticated else None
            
            # Log each event
            unified_logger = UnifiedLoggingService()
            
            for event in events:
                action = event.get('action', 'unknown_action')
                element = event.get('element', {})
                page_url = event.get('page_url', 'unknown')
                
                # Build extra data
                extra_data = {
                    'frontend_event': True,
                    'action': action,
                    'element': element,
                    'page_url': page_url,
                    'page_title': event.get('page_title', ''),
                    'destination': event.get('destination'),
                    'event_timestamp': event.get('timestamp'),
                }
                
                # Log user action
                unified_logger.log_user_action(
                    action=f"frontend_{action}",
                    user=user,
                    resource='frontend',
                    resource_id=element.get('id'),
                    status='success',
                    extra_data=extra_data,
                    request=request,
                    async_log=True
                )
            
            return Response({
                'status': 'success',
                'message': f'Logged {len(events)} events',
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': f'Failed to log events: {str(e)}',
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LogBulkEventsView(APIView):
    """
    API endpoint for bulk logging operations
    Used by services to log multiple events at once
    
    POST /api/v1/logging/bulk/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Log bulk events"""
        try:
            from portal.services.unified_logging_service import UnifiedLoggingService
            
            data = request.data
            events = data.get('events', [])
            
            unified_logger = UnifiedLoggingService()
            
            for event in events:
                event_type = event.get('type', 'user_action')
                
                if event_type == 'user_action':
                    unified_logger.log_user_action(
                        action=event.get('action'),
                        user=request.user,
                        resource=event.get('resource'),
                        resource_id=event.get('resource_id'),
                        status=event.get('status', 'success'),
                        extra_data=event.get('extra_data'),
                        request=request,
                        async_log=True
                    )
                elif event_type == 'service_operation':
                    unified_logger.log_service_operation(
                        service_name=event.get('service_name'),
                        operation=event.get('operation'),
                        user=request.user,
                        status=event.get('status', 'success'),
                        extra_data=event.get('extra_data'),
                        request=request,
                        async_log=True
                    )
            
            return Response({
                'status': 'success',
                'message': f'Logged {len(events)} events',
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'status': 'error',
                'message': f'Failed to log bulk events: {str(e)}',
                'timestamp': timezone.now().isoformat()
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
