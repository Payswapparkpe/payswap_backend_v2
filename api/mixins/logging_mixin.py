"""
API Logging Mixin
Comprehensive logging for DRF API views
"""
from typing import Any
from rest_framework.request import Request
from rest_framework.response import Response


class APILoggingMixin:
    """
    Mixin to add comprehensive logging to DRF API views
    Logs all API operations with request/response bodies
    """
    
    def finalize_response(self, request: Request, response: Response, *args, **kwargs):
        """
        Override finalize_response to log API calls with request/response bodies
        """
        # Call parent implementation
        response = super().finalize_response(request, response, *args, **kwargs)
        
        # Log the API call with bodies
        try:
            from portal.services.unified_logging_service import UnifiedLoggingService
            
            unified_logger = UnifiedLoggingService()
            
            # Extract request body
            request_body = None
            if hasattr(request, 'data') and request.data:
                request_body = dict(request.data) if hasattr(request.data, '__iter__') else str(request.data)
            elif hasattr(request, 'body') and request.body:
                request_body = request.body
            
            # Extract response body
            response_body = None
            if hasattr(response, 'data') and response.data:
                response_body = response.data
            
            # Log via unified service
            unified_logger.log_request_response(
                request=request,
                response=response,
                request_body=request_body,
                response_body=response_body,
                log_level='ERROR' if response.status_code >= 400 else 'INFO'
            )
            
        except Exception as log_error:
            # Don't fail the request if logging fails
            import logging
            logger = logging.getLogger('api.mixins.logging')
            logger.warning(f"Failed to log API call: {str(log_error)}")
        
        return response
    
    def perform_create(self, serializer):
        """Log create operations"""
        try:
            from portal.services.unified_logging_service import UnifiedLoggingService
            
            unified_logger = UnifiedLoggingService()
            
            # Get user
            user = self.request.user if hasattr(self.request, 'user') and self.request.user.is_authenticated else None
            
            # Log operation start
            unified_logger.log_user_action(
                action='api_create',
                user=user,
                resource=self.get_serializer_class().__name__.replace('Serializer', ''),
                status='started',
                extra_data={
                    'data': dict(serializer.validated_data) if hasattr(serializer, 'validated_data') else {}
                },
                request=self.request,
                async_log=True
            )
            
            # Perform create
            result = super().perform_create(serializer)
            
            # Log success
            unified_logger.log_user_action(
                action='api_create',
                user=user,
                resource=self.get_serializer_class().__name__.replace('Serializer', ''),
                resource_id=str(serializer.instance.id) if hasattr(serializer.instance, 'id') else None,
                status='success',
                request=self.request,
                async_log=True
            )
            
            return result
            
        except Exception as e:
            # Log failure
            try:
                from portal.services.unified_logging_service import UnifiedLoggingService
                unified_logger = UnifiedLoggingService()
                
                unified_logger.log_error(
                    exception=e,
                    context={
                        'operation': 'api_create',
                        'resource': self.get_serializer_class().__name__.replace('Serializer', '')
                    },
                    user=self.request.user if hasattr(self.request, 'user') and self.request.user.is_authenticated else None,
                    request=self.request,
                    async_log=True
                )
            except:
                pass  # Don't fail if logging fails
            
            raise
    
    def perform_update(self, serializer):
        """Log update operations"""
        try:
            from portal.services.unified_logging_service import UnifiedLoggingService
            
            unified_logger = UnifiedLoggingService()
            
            # Get user
            user = self.request.user if hasattr(self.request, 'user') and self.request.user.is_authenticated else None
            
            # Get resource ID
            resource_id = str(serializer.instance.id) if hasattr(serializer.instance, 'id') else None
            
            # Log operation start
            unified_logger.log_user_action(
                action='api_update',
                user=user,
                resource=self.get_serializer_class().__name__.replace('Serializer', ''),
                resource_id=resource_id,
                status='started',
                extra_data={
                    'data': dict(serializer.validated_data) if hasattr(serializer, 'validated_data') else {}
                },
                request=self.request,
                async_log=True
            )
            
            # Perform update
            result = super().perform_update(serializer)
            
            # Log success
            unified_logger.log_user_action(
                action='api_update',
                user=user,
                resource=self.get_serializer_class().__name__.replace('Serializer', ''),
                resource_id=resource_id,
                status='success',
                request=self.request,
                async_log=True
            )
            
            return result
            
        except Exception as e:
            # Log failure
            try:
                from portal.services.unified_logging_service import UnifiedLoggingService
                unified_logger = UnifiedLoggingService()
                
                unified_logger.log_error(
                    exception=e,
                    context={
                        'operation': 'api_update',
                        'resource': self.get_serializer_class().__name__.replace('Serializer', ''),
                        'resource_id': resource_id if 'resource_id' in locals() else None
                    },
                    user=self.request.user if hasattr(self.request, 'user') and self.request.user.is_authenticated else None,
                    request=self.request,
                    async_log=True
                )
            except:
                pass  # Don't fail if logging fails
            
            raise
    
    def perform_destroy(self, instance):
        """Log delete operations"""
        try:
            from portal.services.unified_logging_service import UnifiedLoggingService
            
            unified_logger = UnifiedLoggingService()
            
            # Get user
            user = self.request.user if hasattr(self.request, 'user') and self.request.user.is_authenticated else None
            
            # Get resource ID
            resource_id = str(instance.id) if hasattr(instance, 'id') else None
            
            # Log operation start
            unified_logger.log_user_action(
                action='api_delete',
                user=user,
                resource=instance.__class__.__name__,
                resource_id=resource_id,
                status='started',
                request=self.request,
                async_log=True
            )
            
            # Perform delete
            result = super().perform_destroy(instance)
            
            # Log success
            unified_logger.log_user_action(
                action='api_delete',
                user=user,
                resource=instance.__class__.__name__,
                resource_id=resource_id,
                status='success',
                request=self.request,
                async_log=True
            )
            
            return result
            
        except Exception as e:
            # Log failure
            try:
                from portal.services.unified_logging_service import UnifiedLoggingService
                unified_logger = UnifiedLoggingService()
                
                unified_logger.log_error(
                    exception=e,
                    context={
                        'operation': 'api_delete',
                        'resource': instance.__class__.__name__ if 'instance' in locals() else 'unknown',
                        'resource_id': resource_id if 'resource_id' in locals() else None
                    },
                    user=self.request.user if hasattr(self.request, 'user') and self.request.user.is_authenticated else None,
                    request=self.request,
                    async_log=True
                )
            except:
                pass  # Don't fail if logging fails
            
            raise
