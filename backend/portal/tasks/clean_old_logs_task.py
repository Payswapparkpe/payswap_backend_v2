"""
Clean old log files task
Removes log files older than retention period
"""
from celery import shared_task
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from django.conf import settings
from core.config import payswap_config
from portal.tasks.write_logs_task import write_logs_task


@shared_task(name='portal.tasks.clean_old_logs')
def clean_old_logs_task(
    days_to_keep: Optional[int] = None,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Clean old log files based on retention period
    
    Args:
        days_to_keep: Number of days to keep logs (defaults to PAYSWAP_LOG_RETENTION_DAYS)
        request_id: Request ID for tracing
    
    Returns:
        Dict with cleanup summary
    """
    if days_to_keep is None:
        days_to_keep = payswap_config.PAYSWAP_LOG_RETENTION_DAYS
    
    module_name = 'portal.tasks.clean_old_logs'
    logs_dir = Path(settings.BASE_DIR) / payswap_config.PAYSWAP_LOG_DIR
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    
    deleted_files = []
    deleted_size = 0
    errors = []
    
    try:
        # Find all log files
        if logs_dir.exists():
            for log_file in logs_dir.rglob('*.log'):
                # Check file modification time
                file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                
                if file_mtime < cutoff_date:
                    try:
                        file_size = log_file.stat().st_size
                        log_file.unlink()
                        deleted_files.append(str(log_file.relative_to(logs_dir)))
                        deleted_size += file_size
                    except Exception as e:
                        errors.append({'file': str(log_file), 'error': str(e)})
        
        # Log cleanup summary
        write_logs_task.delay(
            log_level='INFO',
            message=f'Log cleanup completed: deleted {len(deleted_files)} files, freed {deleted_size / 1024 / 1024:.2f} MB',
            module_name=module_name,
            url=None,
            request_id=request_id,
            response_id=None,
            user_id=None,
            extra_data={
                'action': 'clean_old_logs',
                'days_to_keep': days_to_keep,
                'deleted_count': len(deleted_files),
                'deleted_size_mb': round(deleted_size / 1024 / 1024, 2),
                'errors': errors if errors else None
            },
            client_ip=None,
            user_agent=None,
            session_id=None
        )
        
        return {
            'success': True,
            'message': f'Cleaned {len(deleted_files)} log files',
            'deleted_files': deleted_files,
            'deleted_size_mb': round(deleted_size / 1024 / 1024, 2),
            'errors': errors if errors else None
        }
        
    except Exception as e:
        write_logs_task.delay(
            log_level='ERROR',
            message=f'Error cleaning old logs: {str(e)}',
            module_name=module_name,
            url=None,
            request_id=request_id,
            response_id=None,
            user_id=None,
            extra_data={
                'action': 'clean_old_logs_error',
                'error': str(e)
            },
            client_ip=None,
            user_agent=None,
            session_id=None
        )
        raise
