"""
Management command: Test API v2 endpoints and check logs for issues.
- Sends requests with X-Api-Explorer header so they are logged under api_explorer.
- Uses API key from --api-key or EXPLORER_DEFAULT_API_KEY from env (auto).
- Use: python manage.py test_api_and_check_logs [--base-url BASE] [--api-key KEY] [--minutes N]
"""
import time
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.test import Client
from django.utils import timezone
from django.conf import settings


def _get_api_key_from_env():
    try:
        from core.config import payswap_config
        key = getattr(payswap_config, "EXPLORER_DEFAULT_API_KEY", None)
        if key is None:
            return None
        if hasattr(key, "get_secret_value"):
            key = key.get_secret_value()
        return (key or "").strip() or None
    except Exception:
        return None


# Endpoints to hit (method, path, optional JSON body for POST)
API_TESTS = [
    ('GET', '/api/v2/health/', None),
    ('GET', '/api/v2/public/', None),
    ('POST', '/api/v2/kyc/pan/verify/', {'pan_number': 'ABCDE1234F'}),
    ('GET', '/api/v2/bbps/operators/', None),
    ('GET', '/api/v2/vendors/', None),
    ('GET', '/api/v2/services/', None),
]


class Command(BaseCommand):
    help = 'Test API v2 endpoints and check logs for errors (API Explorer log system)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--base-url',
            type=str,
            default='http://testserver',
            help='Base URL for requests (default: testserver for Django client)',
        )
        parser.add_argument(
            '--api-key',
            type=str,
            default=None,
            help='API key for X-Api-Key / Authorization; if omitted, uses EXPLORER_DEFAULT_API_KEY from env',
        )
        parser.add_argument(
            '--minutes',
            type=int,
            default=5,
            help='Look back N minutes for log entries (default: 5)',
        )
        parser.add_argument(
            '--skip-requests',
            action='store_true',
            help='Only query and report logs, do not send test requests',
        )

    def handle(self, *args, **options):
        base_url = options['base_url'].rstrip('/')
        api_key = options.get('api_key') or _get_api_key_from_env()
        minutes = options['minutes']
        skip_requests = options['skip_requests']

        if not skip_requests:
            self._run_requests(base_url, api_key)
            # Allow async log tasks to complete
            self.stdout.write('Waiting 4s for async logs...')
            time.sleep(4)

        self._report_logs(minutes)

    def _run_requests(self, base_url, api_key):
        client = Client()
        headers = {'HTTP_X_API_EXPLORER': 'true'}
        if api_key:
            key = api_key.replace('Bearer ', '').strip()
            headers['HTTP_X_API_KEY'] = key
            headers['HTTP_AUTHORIZATION'] = f'Bearer {key}'

        self.stdout.write(self.style.SUCCESS('Sending API Explorer test requests...'))
        for method, path, body in API_TESTS:
            url = path if base_url == 'http://testserver' else base_url + path
            try:
                if method == 'GET':
                    r = client.get(url, **headers)
                else:
                    r = client.post(url, data=body or {}, content_type='application/json', **headers)
                status = r.status_code
                if status >= 400:
                    self.stdout.write(self.style.WARNING(f'  {method} {path} -> {status}'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'  {method} {path} -> {status}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  {method} {path} -> Error: {e}'))

    def _report_logs(self, minutes):
        from portal.models import LogEntry

        since = timezone.now() - timedelta(minutes=minutes)
        all_recent = LogEntry.objects.filter(timestamp__gte=since).order_by('-timestamp')
        explorer_logs = all_recent.filter(category='api_explorer')
        errors = all_recent.filter(log_level='ERROR')
        warnings = all_recent.filter(log_level='WARNING')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== Log summary ==='))
        self.stdout.write(f'  Last {minutes} min: total={all_recent.count()}, api_explorer={explorer_logs.count()}, errors={errors.count()}, warnings={warnings.count()}')

        if errors.exists():
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('--- ERROR entries ---'))
            for e in errors[:20]:
                self.stdout.write(f'  [{e.timestamp}] {e.message}')
                if e.url:
                    self.stdout.write(f'    URL: {e.url}')
                if e.extra_data and (e.extra_data.get('error_message') or e.extra_data.get('response_body')):
                    err_msg = e.extra_data.get('error_message') or str(e.extra_data.get('response_body', ''))[:200]
                    self.stdout.write(f'    Detail: {err_msg}')
                if e.traceback:
                    self.stdout.write(f'    Traceback: {e.traceback[:300]}...')

        if warnings.exists():
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('--- WARNING entries (recent) ---'))
            for w in warnings[:10]:
                self.stdout.write(f'  [{w.timestamp}] {w.message} | {w.url or ""}')

        if warnings.filter(url__icontains='/api/v2/').exists() and not errors.exists():
            self.stdout.write(self.style.WARNING('Tip: 401/403 from API tests are expected without auth. Use --api-key=YOUR_KEY to test protected endpoints.'))

        self.stdout.write('')
        self.stdout.write('View in portal: /logs/?category=api_explorer')
        self.stdout.write('')
