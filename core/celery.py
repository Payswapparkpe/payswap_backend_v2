"""
Celery configuration for Payswap.

Production (1M users): Use named queues so OTP/email are not starved by log volume.
- api_log: write_api_log_task (high volume)
- notifications: OTP, SMS, email (latency-sensitive)
- voucher: bulk voucher issuance (long-running)
- default: everything else (write_logs, log_user_action, etc.)
"""
import os
from celery import Celery
from kombu import Queue

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('payswap')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Named queues for production scaling (see docs/PRODUCTION_CELERY_QUEUES.md).
# Workers must consume these queues; single-worker deploy uses all queues.
app.conf.task_queues = (
    Queue('default', routing_key='default'),
    Queue('api_log', routing_key='api_log'),
    Queue('notifications', routing_key='notifications'),
    Queue('voucher', routing_key='voucher'),
)
app.conf.task_routes = {
    'portal.tasks.send_otp_sms': {'queue': 'notifications'},
    'portal.tasks.send_email': {'queue': 'notifications'},
    'portal.tasks.send_sms': {'queue': 'notifications'},
    'portal.tasks.send_otp_dual': {'queue': 'notifications'},
    'portal.tasks.process_bulk_voucher_issuance': {'queue': 'voucher'},
}

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
