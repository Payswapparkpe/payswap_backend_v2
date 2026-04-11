"""
Service Base Class
Standardized base class for all service layers with common error handling patterns
"""
import logging
import traceback
from typing import Tuple, Optional, Any, Callable
from portal.utils.voucher_logging import log_voucher_operation


class ServiceBase:
    """Base class for services with standardized error handling and logging"""
    
    def __init__(self):
        """Initialize service with logger and unified logging service"""
        self.logger = logging.getLogger(self.__class__.__module__)
        self._unified_logger = None  # Lazy load to avoid circular imports
    
    @property
    def unified_logger(self):
        """Lazy-load unified logging service"""
        if self._unified_logger is None:
            from portal.services.unified_logging_service import UnifiedLoggingService
            self._unified_logger = UnifiedLoggingService()
        return self._unified_logger
    
    def safe_execute(
        self, 
        operation: str, 
        func: Callable, 
        *args, 
        **kwargs
    ) -> Tuple[Any, Optional[str]]:
        """
        Execute a function with standardized error handling and logging
        
        Args:
            operation: Operation name for logging
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Tuple of (result, error_message)
            - On success: (result, None)
            - On failure: (None, error_message)
        """
        try:
            result = func(*args, **kwargs)
            return result, None
        except ValueError as e:
            # Validation errors - log as WARNING
            self.log_error(operation, e, level='WARNING')
            return None, str(e)
        except Exception as e:
            # Unexpected errors - log as ERROR
            self.log_error(operation, e, level='ERROR')
            return None, f"Unexpected error: {str(e)}"
    
    def log_error(
        self, 
        operation: str, 
        exception: Exception, 
        level: str = 'ERROR',
        user_id: Optional[int] = None,
        extra_data: Optional[dict] = None
    ):
        """
        Standardized error logging
        
        Args:
            operation: Operation name
            exception: Exception object
            level: Log level (INFO, WARNING, ERROR, CRITICAL)
            user_id: User ID if available
            extra_data: Additional data to log
        """
        error_message = str(exception)
        exception_type = type(exception).__name__
        trace = traceback.format_exc()
        
        # Log to standard logger
        self.logger.error(
            f"{operation} failed: {error_message}",
            extra={
                'operation': operation,
                'exception_type': exception_type,
                'traceback': trace,
                **(extra_data or {})
            }
        )
        
        # If this is a voucher-related service, also log to voucher logging system
        if 'voucher' in self.__class__.__name__.lower():
            log_voucher_operation(
                operation=operation,
                log_level=level,
                message=f"{operation} failed: {error_message}",
                user_id=user_id,
                extra_data={
                    'exception_type': exception_type,
                    **(extra_data or {})
                },
                exception=exception
            )
    
    def log_info(
        self, 
        operation: str, 
        message: str,
        user_id: Optional[int] = None,
        extra_data: Optional[dict] = None
    ):
        """
        Log informational message
        
        Args:
            operation: Operation name
            message: Log message
            user_id: User ID if available
            extra_data: Additional data to log
        """
        self.logger.info(
            f"{operation}: {message}",
            extra={
                'operation': operation,
                **(extra_data or {})
            }
        )
        
        # If this is a voucher-related service, also log to voucher logging system
        if 'voucher' in self.__class__.__name__.lower():
            log_voucher_operation(
                operation=operation,
                log_level='INFO',
                message=message,
                user_id=user_id,
                extra_data=extra_data
            )
    
    def log_warning(
        self, 
        operation: str, 
        message: str,
        user_id: Optional[int] = None,
        extra_data: Optional[dict] = None
    ):
        """
        Log warning message
        
        Args:
            operation: Operation name
            message: Log message
            user_id: User ID if available
            extra_data: Additional data to log
        """
        self.logger.warning(
            f"{operation}: {message}",
            extra={
                'operation': operation,
                **(extra_data or {})
            }
        )
        
        # If this is a voucher-related service, also log to voucher logging system
        if 'voucher' in self.__class__.__name__.lower():
            log_voucher_operation(
                operation=operation,
                log_level='WARNING',
                message=message,
                user_id=user_id,
                extra_data=extra_data
            )
    
    def validate_required_fields(self, data: dict, required_fields: list) -> Tuple[bool, Optional[str]]:
        """
        Validate that required fields are present and non-empty
        
        Args:
            data: Dictionary of data to validate
            required_fields: List of required field names
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        missing_fields = []
        
        for field in required_fields:
            if field not in data or data[field] is None or data[field] == '':
                missing_fields.append(field)
        
        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            return False, error_msg
        
        return True, None
    
    def log_service_operation(
        self,
        operation: str,
        status: str = 'success',
        user=None,
        extra_data: Optional[dict] = None,
        request=None
    ):
        """
        Log service operation using unified logging service
        
        Args:
            operation: Operation name (e.g., 'create_ticket', 'update_wallet')
            status: Operation status ('started', 'success', 'failed')
            user: User object performing the operation
            extra_data: Additional data to log
            request: Django request object (for context)
        """
        self.unified_logger.log_service_operation(
            service_name=self.__class__.__name__,
            operation=operation,
            user=user,
            status=status,
            extra_data=extra_data,
            request=request,
            async_log=True
        )
    
    def log_operation_error(
        self,
        operation: str,
        exception: Exception,
        user=None,
        context: Optional[dict] = None,
        request=None
    ):
        """
        Log operation error using unified logging service
        
        Args:
            operation: Operation name
            exception: Exception that occurred
            user: User object performing the operation
            context: Context dictionary with operation details
            request: Django request object (for context)
        """
        if context is None:
            context = {}
        context['operation'] = operation
        context['service'] = self.__class__.__name__
        
        self.unified_logger.log_error(
            exception=exception,
            context=context,
            user=user,
            request=request,
            async_log=True
        )
