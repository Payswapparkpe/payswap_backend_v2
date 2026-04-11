"""
Management command to process a batch synchronously (without Celery)
Useful when Celery worker is not running
"""
from django.core.management.base import BaseCommand
from portal.models import BulkVoucherIssuanceBatch
from portal.tasks.voucher_tasks import process_bulk_voucher_issuance_task
from django.utils import timezone


class Command(BaseCommand):
    help = 'Process a voucher batch synchronously (without Celery)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'batch_id',
            type=int,
            help='Batch ID to process'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force process even if status is not PENDING or FAILED'
        )
    
    def handle(self, *args, **options):
        batch_id = options['batch_id']
        force = options.get('force', False)
        
        try:
            batch = BulkVoucherIssuanceBatch.objects.get(id=batch_id)
        except BulkVoucherIssuanceBatch.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Batch {batch_id} not found'))
            return
        
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS(f"Processing Batch: {batch.batch_reference}"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(f"Batch ID: {batch.id}")
        self.stdout.write(f"Status: {batch.status}")
        self.stdout.write(f"Total Vouchers: {batch.total_vouchers}")
        self.stdout.write(f"Method: {batch.issuance_method}")
        self.stdout.write("")
        
        # Check status
        if batch.status == 'PROCESSING':
            if not force:
                self.stdout.write(self.style.WARNING("Batch is already PROCESSING"))
                self.stdout.write("If it's stuck, use --force to reprocess")
                return
            else:
                self.stdout.write(self.style.WARNING("Force processing batch that's already PROCESSING"))
        
        if batch.status == 'COMPLETED':
            if not force:
                self.stdout.write(self.style.WARNING("Batch is already COMPLETED"))
                self.stdout.write("Use --force to reprocess")
                return
        
        # Process synchronously
        self.stdout.write("Starting synchronous processing...")
        self.stdout.write("")
        
        try:
            # Call the task function directly (not .delay())
            result = process_bulk_voucher_issuance_task(batch_id)
            
            # Refresh batch from database
            batch.refresh_from_db()
            
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("=" * 60))
            self.stdout.write(self.style.SUCCESS("Processing Complete"))
            self.stdout.write(self.style.SUCCESS("=" * 60))
            self.stdout.write(f"Final Status: {batch.status}")
            self.stdout.write(f"Successful: {batch.successful_vouchers}")
            self.stdout.write(f"Failed: {batch.failed_vouchers}")
            self.stdout.write(f"Processed: {batch.processed_vouchers}")
            self.stdout.write("")
            self.stdout.write(f"Result: {result}")
            
            if batch.status == 'COMPLETED':
                self.stdout.write(self.style.SUCCESS("✓ Batch processed successfully"))
            elif batch.status == 'FAILED':
                self.stdout.write(self.style.ERROR("✗ Batch processing failed"))
                if batch.error_log:
                    self.stdout.write(f"Error: {batch.error_log}")
            else:
                self.stdout.write(self.style.WARNING(f"⚠ Batch status: {batch.status}"))
                
        except Exception as e:
            import traceback
            self.stdout.write(self.style.ERROR(f"✗ Error processing batch: {e}"))
            self.stdout.write(traceback.format_exc())
            
            # Refresh batch to see final status
            try:
                batch.refresh_from_db()
                self.stdout.write(f"Final batch status: {batch.status}")
            except:
                pass
