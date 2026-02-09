"""
Voucher Export Service - Handles CSV/Excel export of vouchers and batches
"""
import csv
import io
from typing import List, Dict, Any, Optional
from django.http import HttpResponse
from django.db.models import QuerySet
from portal.models import GiftVoucher, BulkVoucherIssuanceBatch
from portal.utils.logging_helper import get_logger
from portal.utils.voucher_logging import log_voucher_operation
from portal.utils.encryption import decrypt_data

logger = get_logger('portal.services.voucher_export')


class VoucherExportService:
    """Service for voucher export operations"""
    
    def export_batch_to_csv(self, batch_id: int) -> HttpResponse:
        """
        Export batch vouchers to CSV
        
        Args:
            batch_id: Batch ID
        
        Returns:
            HttpResponse with CSV file
        """
        try:
            batch = BulkVoucherIssuanceBatch.objects.get(id=batch_id)
            
            # Get all vouchers in this batch
            # Note: We need to track which vouchers belong to which batch
            # For now, we'll use metadata or a separate tracking mechanism
            # Assuming vouchers have batch_id in metadata
            vouchers = GiftVoucher.objects.filter(
                metadata__batch_id=batch_id
            ).select_related('brand', 'client', 'issued_by')
            
            # Create CSV response
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="batch_{batch.batch_reference}_vouchers.csv"'
            
            writer = csv.writer(response)
            
            # Write header
            writer.writerow([
                'Voucher Code',
                'PIN',
                'Amount',
                'Brand Name',
                'Client Name',
                'Issued By',
                'Issuer Type',
                'Batch ID',
                'Batch Reference',
                'Issue Date'
            ])
            
            # Write data rows
            for voucher in vouchers:
                # Get PIN from metadata (encrypted)
                pin = '****'
                if voucher.metadata and 'encrypted_pin' in voucher.metadata:
                    try:
                        pin = decrypt_data(voucher.metadata['encrypted_pin'])
                    except Exception as e:
                        logger.warning(f'Failed to decrypt PIN for voucher {voucher.id}: {str(e)}')
                        pin = '****'
                
                writer.writerow([
                    voucher.voucher_code,
                    pin,  # Actual PIN from metadata
                    str(voucher.original_amount),
                    voucher.brand.brand_name if voucher.brand else '',
                    voucher.client.client_name if voucher.client else '',
                    voucher.issuer_name or (voucher.issued_by.username if voucher.issued_by else ''),
                    voucher.get_issuer_type_display() if voucher.issuer_type else '',
                    batch.id,
                    batch.batch_reference,
                    voucher.issued_at.strftime('%Y-%m-%d %H:%M:%S') if voucher.issued_at else ''
                ])
            
            record_count = vouchers.count()
            log_voucher_operation(
                operation='batch_exported_csv',
                log_level='INFO',
                message=f'Batch exported to CSV - Batch: {batch.batch_reference}, Vouchers: {record_count}',
                extra_data={
                    'batch_id': batch_id,
                    'batch_reference': batch.batch_reference,
                    'record_count': record_count,
                    'format': 'csv'
                }
            )
            
            return response
            
        except BulkVoucherIssuanceBatch.DoesNotExist:
            raise ValueError("Batch not found")
        except Exception as e:
            log_voucher_operation(
                operation='batch_export_failed',
                log_level='ERROR',
                message=f'Failed to export batch to CSV: {str(e)}',
                extra_data={'batch_id': batch_id, 'format': 'csv', 'error': str(e)},
                exception=e
            )
            raise
    
    def export_batch_to_excel(self, batch_id: int) -> HttpResponse:
        """
        Export batch vouchers to Excel
        
        Args:
            batch_id: Batch ID
        
        Returns:
            HttpResponse with Excel file
        """
        try:
            import pandas as pd
            from io import BytesIO
            
            batch = BulkVoucherIssuanceBatch.objects.get(id=batch_id)
            
            # Get all vouchers in this batch
            vouchers = GiftVoucher.objects.filter(
                metadata__batch_id=batch_id
            ).select_related('brand', 'client', 'issued_by')
            
            # Prepare data
            data = []
            for voucher in vouchers:
                # Get PIN from metadata (encrypted)
                pin = '****'
                if voucher.metadata and 'encrypted_pin' in voucher.metadata:
                    try:
                        pin = decrypt_data(voucher.metadata['encrypted_pin'])
                    except Exception as e:
                        logger.warning(f'Failed to decrypt PIN for voucher {voucher.id}: {str(e)}')
                        pin = '****'
                
                data.append({
                    'Voucher Code': voucher.voucher_code,
                    'PIN': pin,  # Actual PIN from metadata
                    'Amount': str(voucher.original_amount),
                    'Brand Name': voucher.brand.brand_name if voucher.brand else '',
                    'Client Name': voucher.client.client_name if voucher.client else '',
                    'Issued By': voucher.issuer_name or (voucher.issued_by.username if voucher.issued_by else ''),
                    'Issuer Type': voucher.get_issuer_type_display() if voucher.issuer_type else '',
                    'Batch ID': batch.id,
                    'Batch Reference': batch.batch_reference,
                    'Issue Date': voucher.issued_at.strftime('%Y-%m-%d %H:%M:%S') if voucher.issued_at else ''
                })
            
            # Create DataFrame
            df = pd.DataFrame(data)
            
            # Create Excel file in memory
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Vouchers', index=False)
                
                # Add batch summary sheet if needed
                if batch.denomination_breakdown:
                    breakdown_data = []
                    for amount_str, denom_data in batch.denomination_breakdown.items():
                        breakdown_data.append({
                            'Amount': amount_str,
                            'Quantity': denom_data.get('quantity', 0),
                            'Successful': denom_data.get('successful', 0),
                            'Failed': denom_data.get('failed', 0)
                        })
                    breakdown_df = pd.DataFrame(breakdown_data)
                    breakdown_df.to_excel(writer, sheet_name='Denomination Breakdown', index=False)
            
            output.seek(0)
            
            # Create response
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="batch_{batch.batch_reference}_vouchers.xlsx"'
            
            record_count = vouchers.count()
            log_voucher_operation(
                operation='batch_exported_excel',
                log_level='INFO',
                message=f'Batch exported to Excel - Batch: {batch.batch_reference}, Vouchers: {record_count}',
                extra_data={
                    'batch_id': batch_id,
                    'batch_reference': batch.batch_reference,
                    'record_count': record_count,
                    'format': 'excel'
                }
            )
            
            return response
            
        except ImportError:
            log_voucher_operation(
                operation='batch_export_failed',
                log_level='ERROR',
                message='Excel export requires pandas and openpyxl',
                extra_data={'batch_id': batch_id, 'format': 'excel', 'error': 'ImportError'}
            )
            raise ValueError("Excel export requires pandas and openpyxl. Please install them.")
        except BulkVoucherIssuanceBatch.DoesNotExist:
            raise ValueError("Batch not found")
        except Exception as e:
            log_voucher_operation(
                operation='batch_export_failed',
                log_level='ERROR',
                message=f'Failed to export batch to Excel: {str(e)}',
                extra_data={'batch_id': batch_id, 'format': 'excel', 'error': str(e)},
                exception=e
            )
            raise
    
    def export_vouchers_by_filters(
        self,
        filters: Dict[str, Any],
        format: str = 'csv'
    ) -> HttpResponse:
        """
        Export vouchers with filters (client, brand, issuer, date range)
        
        Args:
            filters: Dict with brand_id, client_id, issued_by_id, issuer_type, date_from, date_to
            format: Export format ('csv' or 'excel')
        
        Returns:
            HttpResponse with exported file
        """
        try:
            # Build queryset
            vouchers = GiftVoucher.objects.select_related('brand', 'client', 'issued_by')
            
            if filters.get('brand_id'):
                vouchers = vouchers.filter(brand_id=filters['brand_id'])
            if filters.get('client_id'):
                vouchers = vouchers.filter(client_id=filters['client_id'])
            if filters.get('issued_by_id'):
                vouchers = vouchers.filter(issued_by_id=filters['issued_by_id'])
            if filters.get('issuer_type'):
                vouchers = vouchers.filter(issuer_type=filters['issuer_type'])
            if filters.get('date_from'):
                vouchers = vouchers.filter(issued_at__gte=filters['date_from'])
            if filters.get('date_to'):
                vouchers = vouchers.filter(issued_at__lte=filters['date_to'])
            
            record_count = vouchers.count()
            if format == 'csv':
                response = self._export_to_csv(vouchers, filters)
            elif format == 'excel':
                response = self._export_to_excel(vouchers, filters)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            log_voucher_operation(
                operation='vouchers_exported_filtered',
                log_level='INFO',
                message=f'Vouchers exported with filters - Format: {format}, Count: {record_count}',
                extra_data={
                    'format': format,
                    'record_count': record_count,
                    'filters': filters
                }
            )
            
            return response
                
        except Exception as e:
            log_voucher_operation(
                operation='voucher_export_failed',
                log_level='ERROR',
                message=f'Failed to export vouchers by filters: {str(e)}',
                extra_data={'filters': filters, 'format': format, 'error': str(e)},
                exception=e
            )
            raise
    
    def _export_to_csv(self, vouchers: QuerySet, filters: Dict[str, Any]) -> HttpResponse:
        """Helper to export to CSV"""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="vouchers_export.csv"'
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow([
            'Voucher Code',
            'Reference Number',
            'Amount',
            'Balance',
            'Status',
            'Brand Name',
            'Client Name',
            'Issued By',
            'Issuer Type',
            'Issue Date'
        ])
        
        # Write data rows
        for voucher in vouchers:
            writer.writerow([
                voucher.voucher_code,
                voucher.reference_number,
                str(voucher.original_amount),
                str(voucher.current_balance),
                voucher.get_status_display(),
                voucher.brand.brand_name if voucher.brand else '',
                voucher.client.client_name if voucher.client else '',
                voucher.issuer_name or (voucher.issued_by.username if voucher.issued_by else ''),
                voucher.get_issuer_type_display() if voucher.issuer_type else '',
                voucher.issued_at.strftime('%Y-%m-%d %H:%M:%S') if voucher.issued_at else ''
            ])
        
        return response
    
    def _export_to_excel(self, vouchers: QuerySet, filters: Dict[str, Any]) -> HttpResponse:
        """Helper to export to Excel"""
        try:
            import pandas as pd
            from io import BytesIO
            
            # Prepare data
            data = []
            for voucher in vouchers:
                data.append({
                    'Voucher Code': voucher.voucher_code,
                    'Reference Number': voucher.reference_number,
                    'Amount': str(voucher.original_amount),
                    'Balance': str(voucher.current_balance),
                    'Status': voucher.get_status_display(),
                    'Brand Name': voucher.brand.brand_name if voucher.brand else '',
                    'Client Name': voucher.client.client_name if voucher.client else '',
                    'Issued By': voucher.issuer_name or (voucher.issued_by.username if voucher.issued_by else ''),
                    'Issuer Type': voucher.get_issuer_type_display() if voucher.issuer_type else '',
                    'Issue Date': voucher.issued_at.strftime('%Y-%m-%d %H:%M:%S') if voucher.issued_at else ''
                })
            
            # Create DataFrame
            df = pd.DataFrame(data)
            
            # Create Excel file in memory
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Vouchers', index=False)
            
            output.seek(0)
            
            # Create response
            response = HttpResponse(
                output.read(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="vouchers_export.xlsx"'
            
            return response
            
        except ImportError:
            raise ValueError("Excel export requires pandas and openpyxl. Please install them.")
