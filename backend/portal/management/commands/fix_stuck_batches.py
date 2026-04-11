"""
Management command to fix stuck batches (PROCESSING status but not actually processing)
"""
from django.core.management.base import BaseCommand
from portal.models import BulkVoucherIssuanceBatch
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Fix stuck batches that are in PROCESSING status but not actually processing'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=1,
            help='Consider batches stuck if processing for more than N hours (default: 1)'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset stuck batches to PENDING status'
        )
        parser.add_argument(
            '--process',
            action='store_true',
            help='Process stuck batches synchronously'
        )
    
    def handle(self, *args, **options):
        hours = options.get('hours', 1)
        reset = options.get('reset', False)
        process = options.get('process', False)
        
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("Stuck Batch Fixer"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        
        # Find stuck batches
        cutoff_time = timezone.now() - timedelta(hours=hours)
        stuck_batches = BulkVoucherIssuanceBatch.objects.filter(
            status='PROCESSING',
            started_at__lt=cutoff_time
        ).order_by('-started_at')
        
        self.stdout.write(f"\nFound {stuck_batches.count()} stuck batch(es) (processing for >{hours} hour(s))")
        self.stdout.write("")
        
        if stuck_batches.count() == 0:
            self.stdout.write(self.style.SUCCESS("No stuck batches found"))
            return
        
        # List stuck batches
        for batch in stuck_batches:
            elapsed = (timezone.now() - batch.started_at).total_seconds() / 3600
            self.stdout.write(f"Batch ID: {batch.id}")
            self.stdout.write(f"  Reference: {batch.batch_reference}")
            self.stdout.write(f"  Status: {batch.status}")
            self.stdout.write(f"  Started: {batch.started_at}")
            self.stdout.write(f"  Elapsed: {elapsed:.1f} hours")
            self.stdout.write(f"  Total Vouchers: {batch.total_vouchers}")
            self.stdout.write(f"  Processed: {batch.processed_vouchers}")
            self.stdout.write(f"  Successful: {batch.successful_vouchers}")
            self.stdout.write(f"  Failed: {batch.failed_vouchers}")
            self.stdout.write("")
        
        if not reset and not process:
            self.stdout.write(self.style.WARNING("No action specified. Use --reset to reset to PENDING or --process to process synchronously"))
            return
        
        # Reset stuck batches
        if reset:
            self.stdout.write("\nResetting stuck batches to PENDING...")
            for batch in stuck_batches:
                batch.status = 'PENDING'
                batch.started_at = None
                batch.processing_locked_at = None
                batch.processing_locked_by = None
                batch.celery_task_id = None
                batch.save()
                self.stdout.write(self.style.SUCCESS(f"  ✓ Reset batch {batch.batch_reference}"))
        
        # Process stuck batches
        if process:
            from portal.tasks.voucher_tasks import process_bulk_voucher_issuance_task
            
            self.stdout.write("\nProcessing stuck batches synchronously...")
            for batch in stuck_batches:
                self.stdout.write(f"\nProcessing batch {batch.batch_reference}...")
                try:
                    # Reset to PENDING first
                    batch.status = 'PENDING'
                    batch.started_at = None
                    batch.processing_locked_at = None
                    batch.processing_locked_by = None
                    batch.celery_task_id = None
                    batch.save()
                    
                    # Process synchronously
                    result = process_bulk_voucher_issuance_task(batch.id)
                    batch.refresh_from_db()
                    
                    self.stdout.write(f"  Status: {batch.status}")
                    self.stdout.write(f"  Successful: {batch.successful_vouchers}")
                    self.stdout.write(f"  Failed: {batch.failed_vouchers}")
                    
                    if batch.status == 'COMPLETED':
                        self.stdout.write(self.style.SUCCESS(f"  ✓ Batch {batch.batch_reference} processed successfully"))
                    elif batch.status == 'FAILED':
                        self.stdout.write(self.style.ERROR(f"  ✗ Batch {batch.batch_reference} failed: {batch.error_log or 'Unknown error'}"))
                    else:
                        self.stdout.write(self.style.WARNING(f"  ⚠ Batch {batch.batch_reference} status: {batch.status}"))
                        
                except Exception as e:
                    import traceback
                    self.stdout.write(self.style.ERROR(f"  ✗ Error processing batch {batch.batch_reference}: {e}"))
                    self.stdout.write(traceback.format_exc())
        
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("Done"))
