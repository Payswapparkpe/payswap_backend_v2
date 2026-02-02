# Gift Voucher Issuance System - Documentation

## Overview

The Gift Voucher Issuance System is a comprehensive solution for managing gift vouchers, including brand management, voucher issuance (single and bulk), redemption (PIN and OTP-based), PIN management, balance inquiries, and comprehensive reporting.

## Architecture

The system is integrated into the existing `portal` Django app and follows the existing codebase patterns:
- **Models**: Django ORM models with proper indexes and relationships
- **Services**: Business logic layer for voucher operations
- **APIs**: RESTful APIs using Django REST Framework
- **Admin UI**: Django templates with enterprise design system
- **Background Tasks**: Celery for bulk processing and maintenance
- **Security**: PIN/OTP hashing with bcrypt, voucher code encryption, rate limiting
- **Logging**: Comprehensive logging via `LogEntry` model

## Database Models

### GiftVoucherBrand
Brands that issue gift vouchers.

**Fields:**
- `brand_code` (unique): Auto-generated brand identifier
- `brand_name`: Brand name
- `business_reg_no`: Business registration number (optional)
- `contact_person`, `contact_email`, `contact_phone`: Contact details
- `address`: Business address
- `status`: ACTIVE, INACTIVE, or SUSPENDED
- Audit fields: `created_at`, `updated_at`, `created_by`, `updated_by`

### GiftVoucher
Individual gift vouchers.

**Fields:**
- `brand`: Foreign key to GiftVoucherBrand
- `reference_number` (unique): Tracking reference
- `voucher_code` (unique, indexed): 16-digit alphanumeric code
- `voucher_code_hash`: Encrypted voucher code
- `pin_hash`: Hashed 4-digit PIN (bcrypt)
- `original_amount`, `current_balance`: Voucher amounts
- `currency`: Currency code (default: INR)
- `status`: ACTIVE, PARTIALLY_REDEEMED, FULLY_REDEEMED, BLOCKED, EXPIRED
- `mobile_number`: For OTP-based redemption (optional)
- `pin_retry_count`: Failed PIN attempts
- `pin_blocked_until`: Timestamp when PIN block expires
- `pin_history`: JSON array of last 3 PIN hashes
- `metadata`: Additional brand-specific data (JSON)

### GiftVoucherTransaction
All voucher operations (issuance, redemption, balance inquiry, PIN change).

**Fields:**
- `voucher`: Foreign key to GiftVoucher
- `transaction_type`: ISSUANCE, REDEMPTION, BALANCE_INQUIRY, PIN_CHANGE
- `transaction_amount`: Amount (NULL for inquiry/PIN change)
- `balance_before`, `balance_after`: Balance tracking
- `redemption_method`: PIN or OTP (for redemption transactions)
- `transaction_status`: SUCCESS, FAILED, PENDING
- `transaction_ref`: External transaction reference (unique)
- `ip_address`, `user_agent`: Request metadata
- `metadata`: Additional transaction data (JSON)

### GiftVoucherOTP
OTP records for voucher operations.

**Fields:**
- `voucher`: Foreign key to GiftVoucher
- `mobile_number`: Mobile number OTP was sent to
- `otp_hash`: Hashed OTP (bcrypt)
- `otp_purpose`: REDEMPTION or PIN_CHANGE
- `attempt_count`: Verification attempts
- `is_verified`: Whether OTP was verified
- `expires_at`: OTP expiry timestamp
- `generated_at`, `verified_at`: Timestamps

### BulkVoucherIssuanceBatch
Bulk voucher issuance batches.

**Fields:**
- `brand`: Foreign key to GiftVoucherBrand
- `batch_reference` (unique): Batch identifier
- `total_vouchers`, `processed_vouchers`, `successful_vouchers`, `failed_vouchers`: Progress tracking
- `status`: PENDING, PROCESSING, COMPLETED, FAILED
- `uploaded_file_path`, `result_file_path`: S3 file paths
- `started_at`, `completed_at`: Processing timestamps
- `error_log`: Error details (if failed)

### GiftVoucherAuditLog
Audit trail for all voucher operations.

**Fields:**
- `entity_type`, `entity_id`: Entity being audited
- `action`: Action performed
- `user_id`: User who performed action
- `old_values`, `new_values`: JSON fields for change tracking
- `ip_address`, `user_agent`: Request metadata

## API Endpoints

### Brand Management

**Base URL**: `/api/v1/vouchers/brands/`

- `POST /api/v1/vouchers/brands/` - Create brand
- `GET /api/v1/vouchers/brands/` - List brands (paginated, filterable)
- `GET /api/v1/vouchers/brands/{id}/` - Get brand details
- `PUT /api/v1/vouchers/brands/{id}/` - Update brand
- `PATCH /api/v1/vouchers/brands/{id}/status/` - Update brand status

### Voucher Issuance

- **API v2** `POST /api/v2/vouchers/issue/` – Single voucher (partner API key). **`email` is required** for recipient.
  - **Brand identify (sirf ek):** **api_identifier** (6-char alphanumeric, recommended – brand onboard hote hi auto-generate), **brand_id** (integer), ya **brand_code** (string).
  - Request (api_identifier – recommended): `{ "api_identifier": "A1B2C3", "amount": 1000.00, "email": "recipient@example.com", ... }`
  - Request (brand_id): `{ "brand_id": 1, "amount": 1000.00, "email": "recipient@example.com", ... }`
  - Request (brand_code): `{ "brand_code": "PARKPE", "amount": 1000.00, "email": "recipient@example.com", ... }`
  - Response: `{ "voucher_code": "XXXX-XXXX-XXXX-XXXX", "pin": "1234", ... }`
- **Admin / Portal** – Single and bulk issuance: **email is optional** (admin can issue without recipient email).
- `POST /api/v1/vouchers/issue/single/` - Issue single voucher (v1; email optional)
  - Request: `{ "brand_id": 1, "amount": 1000.00, "mobile_number": "9876543210" }`
  - Response: `{ "voucher_code": "XXXX-XXXX-XXXX-XXXX", "pin": "1234", ... }`

- `POST /api/v1/vouchers/issue/bulk/` - Upload bulk file
  - Request: Multipart form with `file` (CSV/Excel) and `brand_id`
  - Response: Batch details with `batch_reference`

- `GET /api/v1/vouchers/issue/bulk/{batch_id}/status/` - Get batch status

### Voucher Redemption

- `POST /api/v1/vouchers/redeem/pin/` - Redeem using PIN
  - Request: `{ "voucher_code": "XXXX-XXXX-XXXX-XXXX", "pin": "1234", "amount": 500.00 }`

- `POST /api/v1/vouchers/redeem/otp/request/` - Request OTP for redemption
  - Request: `{ "voucher_code": "XXXX-XXXX-XXXX-XXXX" }`

- `POST /api/v1/vouchers/redeem/otp/verify/` - Verify OTP and redeem
  - Request: `{ "voucher_code": "XXXX-XXXX-XXXX-XXXX", "otp": "123456", "amount": 500.00 }`

### PIN Management

- `POST /api/v1/vouchers/pin/change/request/` - Request OTP for PIN change
- `POST /api/v1/vouchers/pin/change/verify/` - Verify OTP and change PIN
  - Request: `{ "voucher_code": "XXXX-XXXX-XXXX-XXXX", "otp": "123456", "new_pin": "5678" }`

### Balance Inquiry

- `POST /api/v1/vouchers/balance/` - Check balance
  - Request: `{ "voucher_code": "XXXX-XXXX-XXXX-XXXX", "pin": "1234", "include_transactions": false }`

### Reporting

- `GET /api/v1/vouchers/reports/issuance/` - Issuance report
  - Query params: `brand_id`, `from_date`, `to_date`, `status`, `page`, `limit`

- `GET /api/v1/vouchers/reports/redemption/` - Redemption report
  - Query params: `brand_id`, `from_date`, `to_date`, `page`, `limit`

- `GET /api/v1/vouchers/reports/outstanding/` - Outstanding balance report
  - Query params: `brand_id`, `page`, `limit`

## Admin UI Pages

### Brand Management
- `/vouchers/brands/` - List all brands
- `/vouchers/brands/create/` - Create new brand
- `/vouchers/brands/{brand_id}/` - View/edit brand details

### Voucher Issuance
- `/vouchers/issue/single/` - Issue single voucher
- `/vouchers/issue/single/success/` - Display voucher details after issuance
- `/vouchers/issue/bulk/` - Upload bulk file
- `/vouchers/issue/bulk/{batch_id}/status/` - View batch status and progress

### Voucher Management
- `/vouchers/` - List all vouchers (with filters)
- `/vouchers/search/` - Search voucher by code
- `/vouchers/{voucher_id}/` - View voucher details and transaction history

### Reports
- `/vouchers/reports/issuance/` - Issuance report with filters
- `/vouchers/reports/redemption/` - Redemption report
- `/vouchers/reports/outstanding/` - Outstanding balance report

## Security Features

### PIN Security
- **Hashing**: bcrypt with 12 salt rounds
- **Retry Logic**: Maximum 3 failed attempts
- **Blocking**: 15-minute lockout after max retries
- **History Check**: Prevents reuse of last 3 PINs

### OTP Security
- **Hashing**: bcrypt with 12 salt rounds
- **Validity**: 5 minutes
- **Max Attempts**: 3 verification attempts
- **Cooldown**: 30 seconds between resend requests
- **Auto-cleanup**: Expired OTPs cleaned via Celery task

### Voucher Code Security
- **Encryption**: AES-256 (Fernet) for storage
- **Format**: 16-digit alphanumeric (excludes I, O, 0, 1)
- **Uniqueness**: Database-enforced uniqueness with retry logic

### Rate Limiting
- Voucher validation: 10 requests/minute per IP
- OTP generation: 3 requests/10 minutes per voucher
- PIN attempts: 3 attempts with 15-minute lockout
- API endpoints: 100 requests/minute per API key

## Bulk Processing

### File Format

**CSV Format:**
```csv
amount,mobile_number
1000.00,9876543210
500.00,
2000.00,9876543211
```

**Excel Format:**
Same columns as CSV.

**Requirements:**
- Required column: `amount`
- Optional column: `mobile_number`
- Maximum 10,000 vouchers per batch
- Maximum file size: 10MB

### Processing Flow

1. File upload and validation
2. Parse file and extract voucher data
3. Upload file to S3
4. Create batch record with status PENDING
5. Queue Celery task for processing
6. Process vouchers in chunks of 100
7. Generate result CSV with success/failure status
8. Upload result file to S3
9. Update batch status to COMPLETED

## Error Codes

Standard error codes are defined in `portal/utils/voucher_errors.py`:

- `VOUCHER_NOT_FOUND`: Voucher code does not exist
- `INVALID_PIN`: PIN does not match
- `PIN_LOCKED`: Too many failed attempts, PIN temporarily blocked
- `INSUFFICIENT_BALANCE`: Redemption amount exceeds available balance
- `VOUCHER_BLOCKED`: Voucher is permanently blocked
- `INVALID_OTP`: OTP does not match
- `OTP_EXPIRED`: OTP validity period has expired
- `OTP_MAX_ATTEMPTS`: Maximum OTP verification attempts exceeded
- `PIN_REUSED`: New PIN matches a recently used PIN
- `INVALID_AMOUNT`: Invalid redemption amount
- `BRAND_NOT_FOUND`: Brand does not exist
- `DUPLICATE_TRANSACTION`: Transaction reference already exists
- `VOUCHER_ALREADY_REDEEMED`: Voucher has already been fully redeemed
- `MOBILE_NUMBER_REQUIRED`: Mobile number is required for OTP-based operations

## Background Tasks

### Celery Tasks

1. **process_bulk_voucher_issuance_task**
   - Processes bulk voucher issuance batches
   - Processes in chunks of 100 vouchers
   - Updates batch progress in real-time
   - Generates result CSV file
   - Uploads result file to S3

2. **cleanup_expired_otps_task**
   - Runs every 10 minutes
   - Cleans up expired OTP records

3. **unblock_pin_locked_vouchers_task**
   - Runs every 5 minutes
   - Unblocks vouchers after PIN lockout period expires

## Logging

All voucher operations are logged via `LogEntry` model with category `'gift_voucher'`:

- Brand creation/updates
- Voucher issuance (single and bulk)
- Voucher redemption (PIN and OTP)
- PIN changes
- Balance inquiries
- API errors and exceptions

Logs include:
- User information
- IP address and user agent
- Request/response IDs
- Operation details in `extra_data` JSON field

## Testing

### Unit Tests

- `portal/tests/test_voucher_utils.py`: Voucher code generation, PIN management
- `portal/tests/test_voucher_models.py`: Model validations and relationships
- `api/v1/tests/test_voucher_apis.py`: API endpoint tests

### Integration Tests

- Complete voucher issuance flow
- Redemption flows (PIN and OTP)
- Bulk processing
- OTP generation and verification

## Dependencies

### New Dependencies
- `bcrypt>=4.0.0`: PIN and OTP hashing
- `pandas>=2.0.0`: Excel file processing
- `openpyxl>=3.1.0`: Excel file reading

### Existing Dependencies
- Django, DRF, Celery, Redis, PostgreSQL
- S3 client (boto3)
- Kaleyra SMS service
- Encryption utilities

## Migration

Run the migration to create database tables:

```bash
python manage.py migrate portal
```

This will create all 6 new models with proper indexes and constraints.

## Usage Examples

### Issue Single Voucher (API)

```bash
curl -X POST http://localhost:8000/api/v1/vouchers/issue/single/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "brand_id": 1,
    "amount": 1000.00,
    "mobile_number": "9876543210"
  }'
```

### Redeem Voucher with PIN (API)

```bash
curl -X POST http://localhost:8000/api/v1/vouchers/redeem/pin/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "voucher_code": "ABCD-1234-EFGH-5678",
    "pin": "1234",
    "amount": 500.00
  }'
```

### Check Balance (API)

```bash
curl -X POST http://localhost:8000/api/v1/vouchers/balance/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "voucher_code": "ABCD-1234-EFGH-5678",
    "pin": "1234"
  }'
```

## Notes

- Voucher codes and PINs are shown only once during issuance
- PINs are hashed with bcrypt and cannot be retrieved
- OTPs are sent via SMS using existing Kaleyra integration
- Bulk processing is asynchronous via Celery
- All sensitive operations are logged for audit purposes
- Rate limiting is implemented to prevent abuse
