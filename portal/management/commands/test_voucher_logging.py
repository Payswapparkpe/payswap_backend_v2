"""
Management command to test voucher logging functionality
"""
from django.core.management.base import BaseCommand
from portal.models import LogEntry
from portal.utils.voucher_logging import log_voucher_operation
from portal.utils.logging_utils import categorize_log
from portal.tasks.write_logs_task import write_logs_task
from django.utils import timezone
from django.db.models import Count


class Command(BaseCommand):
    help = 'Test voucher logging functionality and diagnose issues'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Voucher Logging Test Suite"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        
        # Test 1: categorize_log function
        self.stdout.write("\n[Test 1] Testing categorize_log function...")
        try:
            category = categorize_log(
                module_name='portal.views',
                url=None,
                extra_data={'operation': 'voucher_issued'}
            )
            self.stdout.write(f"  Input: module_name='portal.views', extra_data={{'operation': 'voucher_issued'}}")
            self.stdout.write(f"  Output: category='{category}'")
            if category == 'gift_voucher':
                self.stdout.write(self.style.SUCCESS("  ✓ categorize_log correctly returns 'gift_voucher'"))
            else:
                self.stdout.write(self.style.ERROR(f"  ✗ Expected 'gift_voucher', got '{category}'"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ categorize_log failed: {e}"))
        
        # Test 1b: Test without extra_data (should still work)
        self.stdout.write("\n[Test 1b] Testing categorize_log with voucher module name...")
        try:
            category = categorize_log(
                module_name='portal.services.voucher',
                url=None,
                extra_data=None
            )
            self.stdout.write(f"  Input: module_name='portal.services.voucher'")
            self.stdout.write(f"  Output: category='{category}'")
            if category == 'gift_voucher':
                self.stdout.write(self.style.SUCCESS("  ✓ categorize_log correctly detects voucher module"))
            else:
                self.stdout.write(self.style.WARNING(f"  ⚠ Got '{category}' (may be expected)"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ categorize_log failed: {e}"))
        
        # Test 2: Direct write_logs_task call (synchronous)
        self.stdout.write("\n[Test 2] Testing write_logs_task synchronously...")
        try:
            result = write_logs_task(
                log_level='INFO',
                message='Test voucher log from management command',
                module_name='portal.services.voucher',
                url=None,
                extra_data={'operation': 'voucher_issued', 'test': True, 'command': 'test_voucher_logging'},
                user_id=None,
                client_ip='127.0.0.1',
                user_agent='Test Command',
                session_id='test-session'
            )
            self.stdout.write(f"  Task result: {result}")
            if result.get('success'):
                self.stdout.write(self.style.SUCCESS(f"  ✓ write_logs_task executed successfully"))
                self.stdout.write(f"  Category: {result.get('category')}")
            else:
                self.stdout.write(self.style.ERROR(f"  ✗ Task returned success=False"))
        except Exception as e:
            import traceback
            self.stdout.write(self.style.ERROR(f"  ✗ write_logs_task failed: {e}"))
            self.stdout.write(f"  Traceback: {traceback.format_exc()}")
        
        # Test 3: Check database for logs
        self.stdout.write("\n[Test 3] Checking database for logs...")
        try:
            total_logs = LogEntry.objects.count()
            self.stdout.write(f"  Total logs in database: {total_logs}")
            
            gift_voucher_logs = LogEntry.objects.filter(category='gift_voucher')
            self.stdout.write(f"  Total gift_voucher logs: {gift_voucher_logs.count()}")
            
            recent_logs = gift_voucher_logs.order_by('-timestamp')[:5]
            self.stdout.write(f"  Recent gift_voucher logs (last 5):")
            if recent_logs.exists():
                for log in recent_logs:
                    self.stdout.write(f"    - [{log.timestamp}] {log.log_level}: {log.message[:60]}...")
                    self.stdout.write(f"      Category: {log.category}, Module: {log.module_name}")
            else:
                self.stdout.write(self.style.WARNING("    No gift_voucher logs found"))
            
            # Check for test log we just created
            test_logs = LogEntry.objects.filter(
                message__icontains='Test voucher log from management command'
            )
            self.stdout.write(f"\n  Test logs created by this command: {test_logs.count()}")
            for log in test_logs:
                self.stdout.write(f"    - ID: {log.id}, Category: {log.category}, Timestamp: {log.timestamp}")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Database query failed: {e}"))
            import traceback
            self.stdout.write(f"  Traceback: {traceback.format_exc()}")
        
        # Test 4: Test log_voucher_operation (async)
        self.stdout.write("\n[Test 4] Testing log_voucher_operation (queues Celery task)...")
        try:
            log_voucher_operation(
                operation='test_voucher_operation',
                log_level='INFO',
                message='Test voucher operation from management command (async)',
                extra_data={'test': True, 'timestamp': str(timezone.now()), 'command': 'test_voucher_logging'}
            )
            self.stdout.write(self.style.SUCCESS("  ✓ Task queued successfully"))
            self.stdout.write(self.style.WARNING("  ⚠ Note: Task will execute only if Celery worker is running"))
            self.stdout.write("     Check Celery worker logs to verify execution")
            self.stdout.write("     Wait a few seconds and run Test 3 again to see if log appears")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Failed to queue task: {e}"))
            import traceback
            self.stdout.write(f"  Traceback: {traceback.format_exc()}")
        
        # Test 5: Check all categories
        self.stdout.write("\n[Test 5] Checking all log categories...")
        try:
            categories = LogEntry.objects.values('category').annotate(
                count=Count('id')
            ).order_by('-count')
            self.stdout.write("  Category distribution:")
            for cat in categories:
                marker = "✓" if cat['category'] == 'gift_voucher' else " "
                self.stdout.write(f"    {marker} {cat['category']}: {cat['count']} logs")
            
            if not any(cat['category'] == 'gift_voucher' for cat in categories):
                self.stdout.write(self.style.WARNING("\n  ⚠ No 'gift_voucher' category found in database"))
                self.stdout.write("     This could mean:")
                self.stdout.write("     1. No voucher logs have been created yet")
                self.stdout.write("     2. Category is being set incorrectly")
                self.stdout.write("     3. Celery tasks are not executing")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Category query failed: {e}"))
        
        # Test 6: Check for recent logs with operation field
        self.stdout.write("\n[Test 6] Checking logs with 'operation' in extra_data...")
        try:
            from django.db.models import Q
            import json
            
            # Get logs that might be voucher-related based on extra_data
            all_recent = LogEntry.objects.filter(
                timestamp__gte=timezone.now() - timezone.timedelta(hours=24)
            ).order_by('-timestamp')[:20]
            
            voucher_related = []
            for log in all_recent:
                if log.extra_data and isinstance(log.extra_data, dict):
                    operation = log.extra_data.get('operation', '')
                    if any(x in str(operation).lower() for x in ['voucher', 'batch', 'client', 'brand']):
                        voucher_related.append(log)
            
            self.stdout.write(f"  Found {len(voucher_related)} potentially voucher-related logs in last 24 hours")
            for log in voucher_related[:5]:
                operation = log.extra_data.get('operation', 'N/A') if log.extra_data else 'N/A'
                self.stdout.write(f"    - Category: {log.category}, Operation: {operation}")
                self.stdout.write(f"      Message: {log.message[:50]}...")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ✗ Query failed: {e}"))
        
        # Summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Test Summary"))
        self.stdout.write("=" * 60)
        self.stdout.write("\nNext steps:")
        self.stdout.write("1. If Test 2 succeeded but no logs in database:")
        self.stdout.write("   - Check database connection")
        self.stdout.write("   - Check for database errors in logs")
        self.stdout.write("2. If Test 4 queued but no logs appear:")
        self.stdout.write("   - Verify Celery worker is running: celery -A core inspect active")
        self.stdout.write("   - Check Celery worker logs for errors")
        self.stdout.write("3. If logs exist but don't appear on /logs/ page:")
        self.stdout.write("   - Check log page filtering logic")
        self.stdout.write("   - Verify category filter parameter")
        self.stdout.write("4. Access debug page: /logs/debug/")
        self.stdout.write("\n" + "=" * 60)
