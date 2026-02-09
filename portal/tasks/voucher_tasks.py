"""
Celery tasks for gift voucher operations
"""
from celery import shared_task
from typing import Optional, Dict, Any, List
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from portal.models import (
    BulkVoucherIssuanceBatch, GiftVoucher, GiftVoucherTransaction,
    GiftVoucherOTP
)
from portal.services.voucher_service import VoucherService
from portal.services.bulk_voucher_service import BulkVoucherService
from portal.utils.voucher_utils import (
    generate_unique_voucher_code, format_voucher_code,
    generate_pin, hash_pin, generate_reference_number
)
from portal.utils.voucher_encryption import encrypt_voucher_code
from portal.utils.logging_helper import get_logger
from portal.utils.voucher_logging import log_voucher_operation
import traceback

logger = get_logger('portal.tasks.voucher')


@shared_task(name='portal.tasks.process_bulk_voucher_issuance', bind=True, max_retries=3)
def process_bulk_voucher_issuance_task(self, batch_id: int) -> Dict[str, Any]:
    """
    Process bulk voucher issuance batch
    
    Args:
        batch_id: Batch ID to process
    
    Returns:
        Dict with processing result
    """
    try:
        # Phase 2.1: Add select_related to eliminate extra queries
        batch = BulkVoucherIssuanceBatch.objects.select_related(
            'brand', 'client', 'created_by', 'issued_by'
        ).get(id=batch_id)
        
        # Log batch processing start
        user_id = batch.issued_by.id if batch.issued_by and hasattr(batch.issued_by, 'id') else None
        log_voucher_operation(
            operation='batch_processing_started',
            log_level='INFO',
            message=f'Batch processing started - Batch: {batch.batch_reference}, Total: {batch.total_vouchers}',
            user_id=user_id,
            extra_data={
                'batch_id': batch.id,
                'batch_reference': batch.batch_reference,
                'total_vouchers': batch.total_vouchers,
                'brand_id': batch.brand.id if batch.brand else None,
                'brand_name': batch.brand.brand_name if batch.brand else None
            }
        )
        
        # Update status to PROCESSING (if not already)
        # This is idempotent - if view already set it, we don't overwrite
        if batch.status != 'PROCESSING':
            batch.status = 'PROCESSING'
            batch.started_at = timezone.now()
        
        # Initialize progress tracking in metadata (if not already initialized)
        # This is idempotent - if view already initialized it, we preserve existing data
        batch.metadata = batch.metadata or {}
        if 'voucher_progress' not in batch.metadata:
            batch.metadata['voucher_progress'] = {}
        if 'current_voucher_index' not in batch.metadata:
            batch.metadata['current_voucher_index'] = 0
        
        batch.save(update_fields=['status', 'started_at', 'metadata'])
        
        # Get services
        bulk_service = BulkVoucherService()
        voucher_service = VoucherService()
        
        # Check issuance method
        voucher_data = []
        
        if batch.issuance_method == 'MANUAL_BULK':
            # Process from denomination_breakdown
            denomination_breakdown = batch.denomination_breakdown or {}
            row_counter = 1
            
            for amount_str, denom_data in denomination_breakdown.items():
                try:
                    amount = Decimal(amount_str)
                    quantity = denom_data.get('quantity', 0)
                    
                    # Create voucher entries for this denomination
                    for i in range(quantity):
                        voucher_data.append({
                            'row_number': row_counter,
                            'amount': amount,
                            'mobile_number': None,
                            'denomination_amount': amount_str  # Track for breakdown updates
                        })
                        row_counter += 1
                except Exception as e:
                    logger.warning(f'Error processing denomination {amount_str}: {str(e)}')
                    continue
        else:
            # FILE_UPLOAD - Read uploaded file from S3
            from portal.services.vendors.aws_s3 import AWSS3Client
            import csv
            import io
            
            s3_client = AWSS3Client()
            file_path = batch.uploaded_file_path
            
            if not file_path:
                batch.status = 'FAILED'
                batch.error_log = "No file path found for file upload batch"
                batch.completed_at = timezone.now()
                batch.save()
                return {'success': False, 'error': 'No file path found'}
            
            # Extract path from S3 URL or use as-is
            if 'amazonaws.com' in file_path:
                # Extract path from URL
                path = file_path.split('.amazonaws.com/')[-1]
            else:
                path = file_path
            
            # Download file from S3
            try:
                # Read file content
                file_obj = s3_client.s3_client.get_object(
                    Bucket=s3_client.bucket,
                    Key=path
                )
                file_content = file_obj['Body'].read().decode('utf-8-sig')
                
                # Parse CSV
                csv_reader = csv.DictReader(io.StringIO(file_content))
                headers = csv_reader.fieldnames
                if not headers:
                    raise ValueError("CSV file has no headers")
                
                headers_normalized = {h.lower().strip(): h for h in headers}
                
                for row_num, row in enumerate(csv_reader, start=2):
                    try:
                        amount_str = row.get(headers_normalized.get('amount', 'amount'), '').strip()
                        if not amount_str:
                            continue
                        
                        amount = Decimal(amount_str)
                        if amount <= 0:
                            continue
                        
                        mobile_number = None
                        if 'mobile_number' in headers_normalized:
                            mobile_str = row.get(headers_normalized['mobile_number'], '').strip()
                            if mobile_str:
                                mobile_number = mobile_str
                        
                        voucher_data.append({
                            'row_number': row_num,
                            'amount': amount,
                            'mobile_number': mobile_number,
                            'denomination_amount': None  # Not tracked for file uploads
                        })
                    except Exception as e:
                        logger.warning(f'Error parsing row {row_num}: {str(e)}')
                        continue
                
            except Exception as e:
                logger.error(f'Failed to read file from S3: {str(e)}', traceback=traceback.format_exc())
                batch.status = 'FAILED'
                batch.error_log = f"Failed to read file: {str(e)}"
                batch.completed_at = timezone.now()
                batch.processing_locked_at = None
                batch.processing_locked_by = None
                batch.save()
                return {'success': False, 'error': str(e)}
        
        if not voucher_data:
            batch.status = 'FAILED'
            batch.error_log = "No voucher data to process"
            batch.completed_at = timezone.now()
            batch.processing_locked_at = None
            batch.processing_locked_by = None
            batch.save()
            return {'success': False, 'error': 'No voucher data to process'}
        
        # Process vouchers one-by-one for real-time updates
        results = []
        total_rows = len(voucher_data)
        
        # Track denomination breakdown updates for manual bulk
        denomination_updates = {}
        if batch.issuance_method == 'MANUAL_BULK':
            for amount_str in batch.denomination_breakdown.keys():
                denomination_updates[amount_str] = {'successful': 0, 'failed': 0}
        
        # Phase 4.1: Cache brand/client data (already loaded via select_related)
        brand = batch.brand
        client = batch.client
        created_by = batch.created_by
        issued_by = batch.issued_by
        issuer_type = batch.issuer_type
        issuer_name = issued_by.username if issued_by else None
        
        from portal.utils.encryption import encrypt_data
        
        # Process vouchers one-by-one for real-time updates, but use bulk_create in small chunks
        # This gives real-time feedback while maintaining performance
        for item in voucher_data:
            try:
                # Mark voucher as processing in metadata
                batch.metadata = batch.metadata or {}
                batch.metadata['voucher_progress'] = batch.metadata.get('voucher_progress', {})
                batch.metadata['current_voucher_index'] = item['row_number']
                batch.metadata['voucher_progress'][str(item['row_number'])] = {
                    'status': 'processing'
                }
                
                # Save metadata immediately for first 10 vouchers for real-time updates
                if item['row_number'] <= 10:
                    batch.save(update_fields=['metadata'])
                    logger.info(f'Processing voucher {item["row_number"]}/{total_rows} for batch {batch.batch_reference}')
                
                with transaction.atomic():
                    # Generate voucher code and PIN
                    voucher_code = generate_unique_voucher_code()
                    pin = generate_pin()
                    
                    # Encrypt and hash
                    voucher_code_hash = encrypt_voucher_code(voucher_code)
                    pin_hash = hash_pin(pin)
                    
                    # Generate reference number
                    reference_number = generate_reference_number()
                    
                    # Prepare metadata (store PIN encrypted for export purposes)
                    metadata = {
                        'batch_id': batch.id,
                        'batch_reference': batch.batch_reference,
                        'encrypted_pin': encrypt_data(pin)  # Store PIN encrypted for export
                    }
                    if batch.batch_reference_number:
                        metadata['batch_reference_number'] = batch.batch_reference_number
                    
                    # Create voucher
                    voucher = GiftVoucher.objects.create(
                        brand=brand,
                        client=client,
                        reference_number=reference_number,
                        voucher_code=voucher_code,
                        voucher_code_hash=voucher_code_hash,
                        pin_hash=pin_hash,
                        original_amount=item['amount'],
                        current_balance=item['amount'],
                        currency='INR',
                        status='ACTIVE',
                        mobile_number=item.get('mobile_number'),
                        created_by=created_by,
                        issued_by=issued_by,
                        issuer_type=issuer_type,
                        issuer_name=issuer_name,
                        metadata=metadata
                    )
                    
                    # Create issuance transaction
                    GiftVoucherTransaction.objects.create(
                        voucher=voucher,
                        transaction_type='ISSUANCE',
                        transaction_amount=None,
                        balance_before=Decimal('0.00'),
                        balance_after=item['amount'],
                        transaction_status='SUCCESS',
                        metadata={'reference_number': reference_number, 'batch_id': batch.id}
                    )
                    
                    # Update denomination breakdown if manual bulk
                    if batch.issuance_method == 'MANUAL_BULK' and item.get('denomination_amount'):
                        denom_amount = item['denomination_amount']
                        if denom_amount in denomination_updates:
                            denomination_updates[denom_amount]['successful'] += 1
                    
                    # Update batch counters and metadata
                    batch.successful_vouchers += 1
                    batch.processed_vouchers += 1
                    batch.metadata['voucher_progress'][str(item['row_number'])] = {
                        'status': 'completed',
                        'voucher_id': voucher.id,
                        'voucher_code': format_voucher_code(voucher_code),
                        'processed_at': timezone.now().isoformat()
                    }
                    
                    # Add to results
                    results.append({
                        'row_number': item['row_number'],
                        'reference_number': reference_number,
                        'voucher_code': format_voucher_code(voucher_code),
                        'pin': pin,
                        'amount': str(item['amount']),
                        'status': 'SUCCESS',
                        'error_message': ''
                    })
                    
                    # Save metadata and counters - every voucher for first 10, then every 10 vouchers
                    if item['row_number'] <= 10 or item['row_number'] % 10 == 0 or item['row_number'] == total_rows:
                        batch.save(update_fields=['successful_vouchers', 'processed_vouchers', 'metadata'])
                        if item['row_number'] <= 10:
                            logger.info(f'Completed voucher {item["row_number"]}/{total_rows} for batch {batch.batch_reference}')
                    else:
                        # Only save counters if not saving metadata
                        batch.save(update_fields=['successful_vouchers', 'processed_vouchers'])
                    
                    # Log progress every 10 vouchers
                    if item['row_number'] % 10 == 0:
                        logger.info(
                            f'Batch {batch.batch_reference} progress: {batch.processed_vouchers}/{batch.total_vouchers} '
                            f'({int((batch.processed_vouchers/batch.total_vouchers)*100)}%)'
                        )
                    
            except Exception as e:
                log_voucher_operation(
                    operation='voucher_creation_failed_in_batch',
                    log_level='ERROR',
                    message=f'Error creating voucher for row {item["row_number"]} in batch {batch.batch_reference}: {str(e)}',
                    extra_data={
                        'batch_id': batch.id,
                        'batch_reference': batch.batch_reference,
                        'row_number': item['row_number'],
                        'amount': str(item['amount']),
                        'error': str(e)
                    },
                    exception=e
                )
                
                # Update denomination breakdown on failure
                if batch.issuance_method == 'MANUAL_BULK' and item.get('denomination_amount'):
                    denom_amount = item['denomination_amount']
                    if denom_amount in denomination_updates:
                        denomination_updates[denom_amount]['failed'] += 1
                
                results.append({
                    'row_number': item['row_number'],
                    'reference_number': '',
                    'voucher_code': '',
                    'pin': '',
                    'amount': str(item['amount']),
                    'status': 'FAILED',
                    'error_message': str(e)
                })
                
                # Update batch counters and metadata for failed voucher
                batch.failed_vouchers += 1
                batch.processed_vouchers += 1
                
                batch.metadata['voucher_progress'][str(item['row_number'])] = {
                    'status': 'failed',
                    'error': str(e)[:200],
                    'processed_at': timezone.now().isoformat()
                }
                
                # Save counters periodically
                if item['row_number'] % 10 == 0 or item['row_number'] == total_rows:
                    batch.save(update_fields=['failed_vouchers', 'processed_vouchers', 'metadata'])
                else:
                    batch.save(update_fields=['failed_vouchers', 'processed_vouchers'])
        
        # Ensure final metadata is saved (in case last voucher wasn't at interval boundary)
        batch.refresh_from_db()
        if batch.metadata and batch.metadata.get('voucher_progress'):
            batch.save(update_fields=['metadata'])
        
        # Update denomination breakdown with success/failure counts
        if batch.issuance_method == 'MANUAL_BULK' and denomination_updates:
            updated_breakdown = batch.denomination_breakdown.copy()
            for amount_str, updates in denomination_updates.items():
                if amount_str in updated_breakdown:
                    updated_breakdown[amount_str]['successful'] = updates['successful']
                    updated_breakdown[amount_str]['failed'] = updates['failed']
            batch.denomination_breakdown = updated_breakdown
        
        # Generate result file
        result_csv = bulk_service.generate_result_file(batch, results)
        
        # Upload result file to S3
        try:
            result_file_path = bulk_service.upload_result_file_to_s3(result_csv, batch.id)
            batch.result_file_path = result_file_path
        except Exception as e:
            logger.error(f'Failed to upload result file: {str(e)}')
            # Continue without result file
        
        # Update batch status and release lock
        batch.status = 'COMPLETED'
        batch.completed_at = timezone.now()
        batch.processing_locked_at = None
        batch.processing_locked_by = None
        batch.save()
        
        log_voucher_operation(
            operation='batch_processing_completed',
            log_level='INFO',
            message=f'Batch processing completed - Batch: {batch.batch_reference}, Success: {batch.successful_vouchers}, Failed: {batch.failed_vouchers}',
            user_id=user_id,
            extra_data={
                'batch_id': batch.id,
                'batch_reference': batch.batch_reference,
                'total_vouchers': batch.total_vouchers,
                'successful_vouchers': batch.successful_vouchers,
                'failed_vouchers': batch.failed_vouchers,
                'processed_vouchers': batch.processed_vouchers,
                'brand_id': batch.brand.id if batch.brand else None,
                'brand_name': batch.brand.brand_name if batch.brand else None
            }
        )
        
        return {
            'success': True,
            'batch_id': batch.id,
            'batch_reference': batch.batch_reference,
            'total_vouchers': batch.total_vouchers,
            'successful_vouchers': batch.successful_vouchers,
            'failed_vouchers': batch.failed_vouchers
        }
        
    except BulkVoucherIssuanceBatch.DoesNotExist:
        log_voucher_operation(
            operation='batch_processing_failed',
            log_level='ERROR',
            message=f'Batch {batch_id} not found',
            extra_data={'batch_id': batch_id, 'error': 'Batch not found'}
        )
        return {'success': False, 'error': 'Batch not found'}
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        
        # Get user_id if batch was loaded
        error_user_id = None
        try:
            if 'batch' in locals() and batch and batch.issued_by:
                error_user_id = batch.issued_by.id if hasattr(batch.issued_by, 'id') else None
        except Exception:
            pass
        
        log_voucher_operation(
            operation='batch_processing_failed',
            log_level='ERROR',
            message=f'Error processing bulk issuance: {str(e)}',
            user_id=error_user_id,
            extra_data={
                'batch_id': batch_id, 
                'error': str(e), 
                'traceback': error_traceback[:500]
            },
            exception=e
        )
        
        # CRITICAL: Always update batch status on failure
        try:
            batch = BulkVoucherIssuanceBatch.objects.get(id=batch_id)
            batch.status = 'FAILED'
            batch.error_log = f"{str(e)}\n\nTraceback:\n{error_traceback[:1000]}"
            batch.completed_at = timezone.now()
            batch.processing_locked_at = None
            batch.processing_locked_by = None
            batch.save()
            logger.error(f'Batch {batch_id} marked as FAILED: {str(e)}')
        except Exception as db_error:
            logger.error(f'Failed to update batch status: {str(db_error)}')
        
        # Only retry if it's a transient error and we haven't exceeded max retries
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        else:
            # Max retries reached, don't retry again
            logger.error(f'Max retries reached for batch {batch_id}, giving up')
            return {'success': False, 'error': str(e), 'max_retries_reached': True}


@shared_task(name='portal.tasks.cleanup_expired_voucher_otps', bind=True)
def cleanup_expired_otps_task(self) -> Dict[str, Any]:
    """
    Clean up expired OTP records (runs every 10 minutes)
    
    Returns:
        Dict with cleanup result
    """
    try:
        from portal.services.voucher_otp_service import VoucherOTPService
        
        otp_service = VoucherOTPService()
        cleaned_count = otp_service.cleanup_expired_otps()
        
        logger.info(f'Cleaned up {cleaned_count} expired OTP records')
        
        return {
            'success': True,
            'cleaned_count': cleaned_count
        }
    except Exception as e:
        logger.error(f'Error cleaning up expired OTPs: {str(e)}', traceback=traceback.format_exc())
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(name='portal.tasks.unblock_pin_locked_vouchers', bind=True)
def unblock_pin_locked_vouchers_task(self) -> Dict[str, Any]:
    """
    Unblock vouchers after PIN lockout period (runs every 5 minutes)
    
    Returns:
        Dict with unblock result
    """
    try:
        from portal.models import GiftVoucher
        from portal.utils.voucher_utils import is_pin_blocked
        
        # Find vouchers that are blocked but should be unblocked now
        now = timezone.now()
        vouchers_to_unblock = GiftVoucher.objects.filter(
            pin_blocked_until__isnull=False,
            pin_blocked_until__lt=now
        )
        
        unblocked_count = 0
        for voucher in vouchers_to_unblock:
            voucher.pin_blocked_until = None
            voucher.pin_retry_count = 0
            voucher.save()
            unblocked_count += 1
        
        if unblocked_count > 0:
            logger.info(f'Unblocked {unblocked_count} vouchers after PIN lockout period')
        
        return {
            'success': True,
            'unblocked_count': unblocked_count
        }
    except Exception as e:
        logger.error(f'Error unblocking vouchers: {str(e)}', traceback=traceback.format_exc())
        return {
            'success': False,
            'error': str(e)
        }
