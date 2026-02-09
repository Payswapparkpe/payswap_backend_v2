"""
Bulk Voucher Service - Handles bulk voucher issuance file processing
"""
import csv
import io
from typing import List, Dict, Any, Tuple, Optional
from decimal import Decimal, InvalidOperation
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone
from portal.models import GiftVoucherBrand, BulkVoucherIssuanceBatch, VoucherClient, User
from portal.utils.voucher_utils import generate_reference_number
from portal.utils.logging_helper import get_logger
from portal.utils.voucher_logging import log_voucher_operation
from portal.services.voucher_client_service import VoucherClientService

logger = get_logger('portal.services.bulk_voucher')

MAX_BULK_VOUCHERS = 10000
MIN_BULK_VOUCHERS = 1
CHUNK_SIZE = 100


class BulkVoucherService:
    """Service for bulk voucher operations"""
    
    def validate_upload_file(self, file: UploadedFile) -> Tuple[bool, Optional[str]]:
        """
        Validate uploaded file format
        
        Args:
            file: Uploaded file
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check file extension
        file_name = file.name.lower()
        if not (file_name.endswith('.csv') or file_name.endswith('.xlsx') or file_name.endswith('.xls')):
            log_voucher_operation(
                operation='file_validation_failed',
                log_level='WARNING',
                message=f'Invalid file format uploaded: {file_name}',
                extra_data={'file_name': file_name, 'file_size': file.size, 'reason': 'invalid_format'}
            )
            return False, "Invalid file format. Only CSV and Excel files are supported."
        
        # Check file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if file.size > max_size:
            log_voucher_operation(
                operation='file_validation_failed',
                log_level='WARNING',
                message=f'File size exceeds limit: {file_name}',
                extra_data={'file_name': file_name, 'file_size': file.size, 'max_size': max_size, 'reason': 'size_exceeded'}
            )
            return False, f"File size exceeds maximum limit of {max_size / (1024*1024)}MB"
        
        log_voucher_operation(
            operation='file_validated',
            log_level='INFO',
            message=f'File validated successfully: {file_name}',
            extra_data={'file_name': file_name, 'file_size': file.size}
        )
        return True, None
    
    def parse_csv_file(self, file: UploadedFile) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Parse CSV file and extract voucher data
        
        Args:
            file: Uploaded CSV file
        
        Returns:
            Tuple of (voucher_data_list, error_message)
        """
        try:
            # Reset file pointer
            file.seek(0)
            
            # Read file content
            content = file.read().decode('utf-8-sig')  # Handle BOM
            file.seek(0)
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(content))
            
            # Check required headers
            required_headers = ['amount']
            headers = csv_reader.fieldnames
            
            if not headers:
                return [], "CSV file is empty or invalid"
            
            # Normalize headers (lowercase, strip spaces)
            headers_normalized = {h.lower().strip(): h for h in headers}
            
            # Check required headers
            missing_headers = []
            for req_header in required_headers:
                if req_header not in headers_normalized:
                    missing_headers.append(req_header)
            
            if missing_headers:
                return [], f"Missing required columns: {', '.join(missing_headers)}"
            
            # Parse rows
            voucher_data = []
            errors = []
            
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (row 1 is header)
                try:
                    # Get amount
                    amount_str = row.get(headers_normalized['amount'], '').strip()
                    if not amount_str:
                        errors.append(f"Row {row_num}: Amount is required")
                        continue
                    
                    try:
                        amount = Decimal(amount_str)
                        if amount <= 0:
                            errors.append(f"Row {row_num}: Amount must be greater than 0")
                            continue
                    except (InvalidOperation, ValueError):
                        errors.append(f"Row {row_num}: Invalid amount format")
                        continue
                    
                    # Get mobile number (optional)
                    mobile_number = None
                    if 'mobile_number' in headers_normalized:
                        mobile_str = row.get(headers_normalized['mobile_number'], '').strip()
                        if mobile_str:
                            mobile_number = mobile_str
                    
                    voucher_data.append({
                        'row_number': row_num,
                        'amount': amount,
                        'mobile_number': mobile_number
                    })
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: Error parsing row - {str(e)}")
            
            # Check total count
            if len(voucher_data) > MAX_BULK_VOUCHERS:
                return [], f"Maximum {MAX_BULK_VOUCHERS} vouchers allowed per batch. Found {len(voucher_data)}."
            
            if len(voucher_data) < MIN_BULK_VOUCHERS:
                return [], f"Minimum {MIN_BULK_VOUCHERS} voucher required. Found {len(voucher_data)}."
            
            # Return errors if any (but still return data if some rows are valid)
            error_message = None
            if errors:
                error_message = f"Found {len(errors)} error(s) in file. Processing will continue for valid rows."
                log_voucher_operation(
                    operation='csv_parsing_errors',
                    log_level='WARNING',
                    message=f'CSV parsing found {len(errors)} error(s)',
                    extra_data={'file_name': file.name, 'row_count': len(voucher_data), 'error_count': len(errors), 'errors': errors[:10]}
                )
            
            log_voucher_operation(
                operation='csv_parsed',
                log_level='INFO',
                message=f'CSV file parsed successfully: {file.name}',
                extra_data={'file_name': file.name, 'row_count': len(voucher_data), 'error_count': len(errors) if errors else 0}
            )
            return voucher_data, error_message
            
        except Exception as e:
            log_voucher_operation(
                operation='csv_parsing_failed',
                log_level='ERROR',
                message=f'Failed to parse CSV file: {str(e)}',
                extra_data={'file_name': file.name, 'error': str(e)},
                exception=e
            )
            return [], f"Failed to parse CSV file: {str(e)}"
    
    def parse_excel_file(self, file: UploadedFile) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Parse Excel file and extract voucher data
        
        Args:
            file: Uploaded Excel file
        
        Returns:
            Tuple of (voucher_data_list, error_message)
        """
        try:
            import pandas as pd
            
            # Reset file pointer
            file.seek(0)
            
            # Read Excel file
            df = pd.read_excel(file, engine='openpyxl')
            
            # Check required columns
            required_columns = ['amount']
            missing_columns = [col for col in required_columns if col.lower() not in [c.lower() for c in df.columns]]
            
            if missing_columns:
                return [], f"Missing required columns: {', '.join(missing_columns)}"
            
            # Normalize column names (lowercase)
            df.columns = df.columns.str.lower().str.strip()
            
            # Parse rows
            voucher_data = []
            errors = []
            
            for idx, row in df.iterrows():
                row_num = idx + 2  # Excel row number (row 1 is header)
                
                try:
                    # Get amount
                    amount_val = row.get('amount')
                    if pd.isna(amount_val) or amount_val == '':
                        errors.append(f"Row {row_num}: Amount is required")
                        continue
                    
                    try:
                        amount = Decimal(str(amount_val))
                        if amount <= 0:
                            errors.append(f"Row {row_num}: Amount must be greater than 0")
                            continue
                    except (InvalidOperation, ValueError):
                        errors.append(f"Row {row_num}: Invalid amount format")
                        continue
                    
                    # Get mobile number (optional)
                    mobile_number = None
                    if 'mobile_number' in df.columns:
                        mobile_val = row.get('mobile_number')
                        if not pd.isna(mobile_val) and mobile_val != '':
                            mobile_number = str(mobile_val).strip()
                    
                    voucher_data.append({
                        'row_number': row_num,
                        'amount': amount,
                        'mobile_number': mobile_number
                    })
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: Error parsing row - {str(e)}")
            
            # Check total count
            if len(voucher_data) > MAX_BULK_VOUCHERS:
                return [], f"Maximum {MAX_BULK_VOUCHERS} vouchers allowed per batch. Found {len(voucher_data)}."
            
            if len(voucher_data) < MIN_BULK_VOUCHERS:
                return [], f"Minimum {MIN_BULK_VOUCHERS} voucher required. Found {len(voucher_data)}."
            
            # Return errors if any
            error_message = None
            if errors:
                error_message = f"Found {len(errors)} error(s) in file. Processing will continue for valid rows."
                log_voucher_operation(
                    operation='excel_parsing_errors',
                    log_level='WARNING',
                    message=f'Excel parsing found {len(errors)} error(s)',
                    extra_data={'file_name': file.name, 'row_count': len(voucher_data), 'error_count': len(errors), 'errors': errors[:10]}
                )
            
            log_voucher_operation(
                operation='excel_parsed',
                log_level='INFO',
                message=f'Excel file parsed successfully: {file.name}',
                extra_data={'file_name': file.name, 'row_count': len(voucher_data), 'error_count': len(errors) if errors else 0}
            )
            return voucher_data, error_message
            
        except ImportError:
            log_voucher_operation(
                operation='excel_parsing_failed',
                log_level='ERROR',
                message='Excel file processing requires pandas and openpyxl',
                extra_data={'file_name': file.name, 'error': 'ImportError'}
            )
            return [], "Excel file processing requires pandas and openpyxl. Please install them or use CSV format."
        except Exception as e:
            log_voucher_operation(
                operation='excel_parsing_failed',
                log_level='ERROR',
                message=f'Failed to parse Excel file: {str(e)}',
                extra_data={'file_name': file.name, 'error': str(e)},
                exception=e
            )
            return [], f"Failed to parse Excel file: {str(e)}"
    
    def parse_upload_file(self, file: UploadedFile) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Parse uploaded file (CSV or Excel)
        
        Args:
            file: Uploaded file
        
        Returns:
            Tuple of (voucher_data_list, error_message)
        """
        file_name = file.name.lower()
        
        if file_name.endswith('.csv'):
            return self.parse_csv_file(file)
        elif file_name.endswith('.xlsx') or file_name.endswith('.xls'):
            return self.parse_excel_file(file)
        else:
            return [], "Unsupported file format"
    
    def generate_result_file(
        self,
        batch: BulkVoucherIssuanceBatch,
        results: List[Dict[str, Any]]
    ) -> str:
        """
        Generate result CSV file with voucher details
        
        Args:
            batch: Batch instance
            results: List of result dicts with voucher details
        
        Returns:
            CSV content as string
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'row_number',
            'reference_number',
            'voucher_code',
            'pin',
            'amount',
            'status',
            'error_message'
        ])
        
        # Write data rows
        for result in results:
            writer.writerow([
                result.get('row_number', ''),
                result.get('reference_number', ''),
                result.get('voucher_code', ''),
                result.get('pin', ''),
                result.get('amount', ''),
                result.get('status', ''),
                result.get('error_message', '')
            ])
        
        return output.getvalue()
    
    def upload_file_to_s3(self, file: UploadedFile, batch_id: int) -> str:
        """
        Upload file to S3
        
        Args:
            file: File to upload
            batch_id: Batch ID
        
        Returns:
            S3 path
        """
        from portal.services.vendors.aws_s3 import AWSS3Client
        
        s3_client = AWSS3Client()
        path = f"vouchers/bulk/{batch_id}/upload.{file.name.split('.')[-1]}"
        
        # Upload file
        s3_url = s3_client.upload_file(file, path)
        
        return s3_url
    
    def upload_result_file_to_s3(self, csv_content: str, batch_id: int) -> str:
        """
        Upload result CSV file to S3
        
        Args:
            csv_content: CSV content as string
            batch_id: Batch ID
        
        Returns:
            S3 path
        """
        from portal.services.vendors.aws_s3 import AWSS3Client
        from django.core.files.base import ContentFile
        
        s3_client = AWSS3Client()
        path = f"vouchers/bulk/{batch_id}/result.csv"
        
        # Create file-like object
        file_obj = ContentFile(csv_content.encode('utf-8'))
        file_obj.name = 'result.csv'
        
        # Upload file
        s3_url = s3_client.upload_file(file_obj, path)
        
        return s3_url
    
    def create_manual_bulk_batch(
        self,
        brand_id: int,
        client_id: Optional[int],
        denominations: List[Dict[str, Any]],
        issued_by: User,
        issuer_type: str
    ) -> BulkVoucherIssuanceBatch:
        """
        Create manual bulk issuance batch with multi-denomination support
        
        Args:
            brand_id: Brand ID
            client_id: Optional client ID (defaults to Payswap client)
            denominations: List of dicts with 'amount' and 'quantity'
            issued_by: User who issued the batch
            issuer_type: Type of issuer (ADMIN/API_PARTNER/BRAND_OWNER)
        
        Returns:
            BulkVoucherIssuanceBatch instance
        """
        try:
            # Get brand
            try:
                brand = GiftVoucherBrand.objects.get(id=brand_id)
            except GiftVoucherBrand.DoesNotExist:
                raise ValueError("Brand not found")
            
            # Validate brand can issue vouchers
            if not brand.can_issue_vouchers():
                raise ValueError("Brand cannot issue vouchers. Please complete onboarding first.")
            
            # Get or create default client if client_id not provided
            client_service = VoucherClientService()
            if client_id:
                try:
                    client = VoucherClient.objects.get(id=client_id, brand=brand, status='ACTIVE')
                except VoucherClient.DoesNotExist:
                    raise ValueError("Client not found or inactive")
            else:
                client = client_service.get_or_create_default_client(brand_id)
            
            # Validate denominations
            if not denominations or len(denominations) == 0:
                raise ValueError("At least one denomination is required")
            
            total_vouchers = 0
            denomination_breakdown = {}
            
            for denom in denominations:
                amount = Decimal(str(denom.get('amount', 0)))
                quantity = int(denom.get('quantity', 0))
                
                if amount <= 0:
                    raise ValueError(f"Invalid amount: {amount}. Amount must be greater than 0")
                if quantity <= 0:
                    raise ValueError(f"Invalid quantity: {quantity}. Quantity must be greater than 0")
                
                total_vouchers += quantity
                denomination_breakdown[str(amount)] = {
                    'quantity': quantity,
                    'successful': 0,
                    'failed': 0
                }
            
            # Check total count
            if total_vouchers > MAX_BULK_VOUCHERS:
                raise ValueError(f"Maximum {MAX_BULK_VOUCHERS} vouchers allowed per batch. Requested {total_vouchers}.")
            if total_vouchers < MIN_BULK_VOUCHERS:
                raise ValueError(f"Minimum {MIN_BULK_VOUCHERS} voucher required. Requested {total_vouchers}.")
            
            # Generate batch reference
            batch_reference = generate_reference_number('BATCH')
            batch_reference_number = generate_reference_number('BRN')
            
            # Generate issuer name
            issuer_name = None
            if hasattr(issued_by, 'username'):
                issuer_name = issued_by.username
            elif hasattr(issued_by, 'get_full_name'):
                issuer_name = issued_by.get_full_name()
            else:
                issuer_name = str(issued_by)
            
            # Create batch
            with transaction.atomic():
                batch = BulkVoucherIssuanceBatch.objects.create(
                    brand=brand,
                    client=client,
                    batch_reference=batch_reference,
                    batch_reference_number=batch_reference_number,
                    total_vouchers=total_vouchers,
                    status='PENDING',
                    issuance_method='MANUAL_BULK',
                    issued_by=issued_by,
                    issuer_type=issuer_type,
                    denomination_breakdown=denomination_breakdown,
                    created_by=issued_by
                )
            
            user_id = issued_by.id if hasattr(issued_by, 'id') else None
            log_voucher_operation(
                operation='batch_created',
                log_level='INFO',
                message=f'Manual bulk batch created - Batch: {batch_reference}, Brand: {brand.brand_name}, Total: {total_vouchers}',
                user_id=user_id,
                extra_data={
                    'batch_id': batch.id,
                    'batch_reference': batch_reference,
                    'brand_id': brand_id,
                    'brand_name': brand.brand_name,
                    'client_id': client.id,
                    'client_name': client.client_name,
                    'total_vouchers': total_vouchers,
                    'denomination_count': len(denominations),
                    'denominations': [{'amount': str(d.get('amount', 0)), 'quantity': d.get('quantity', 0)} for d in denominations],
                    'issuer_type': issuer_type
                }
            )
            
            return batch
            
        except Exception as e:
            user_id = issued_by.id if hasattr(issued_by, 'id') else None
            log_voucher_operation(
                operation='batch_creation_failed',
                log_level='ERROR',
                message=f'Failed to create manual bulk batch: {str(e)}',
                user_id=user_id,
                extra_data={'brand_id': brand_id, 'error': str(e)},
                exception=e
            )
            raise
    
    def generate_denomination_breakdown(self, batch: BulkVoucherIssuanceBatch) -> Dict[str, Any]:
        """
        Generate denomination breakdown report for a batch
        
        Args:
            batch: BulkVoucherIssuanceBatch instance
        
        Returns:
            Dict with breakdown details
        """
        breakdown = batch.denomination_breakdown or {}
        
        result = {
            'total_denominations': len(breakdown),
            'denominations': [],
            'summary': {
                'total_requested': batch.total_vouchers,
                'total_successful': batch.successful_vouchers,
                'total_failed': batch.failed_vouchers,
                'total_processed': batch.processed_vouchers
            }
        }
        
        for amount_str, data in breakdown.items():
            amount = Decimal(amount_str)
            quantity = data.get('quantity', 0)
            successful = data.get('successful', 0)
            failed = data.get('failed', 0)
            
            result['denominations'].append({
                'amount': str(amount),
                'quantity': quantity,
                'successful': successful,
                'failed': failed,
                'pending': quantity - successful - failed,
                'total_value': str(amount * quantity),
                'successful_value': str(amount * successful)
            })
        
        # Sort by amount
        result['denominations'].sort(key=lambda x: Decimal(x['amount']), reverse=True)
        
        log_voucher_operation(
            operation='denomination_breakdown_generated',
            log_level='INFO',
            message=f'Denomination breakdown generated for batch {batch.batch_reference}',
            extra_data={
                'batch_id': batch.id,
                'batch_reference': batch.batch_reference,
                'total_denominations': len(breakdown),
                'summary': result['summary']
            }
        )
        
        return result
