# Unified Notification Service Implementation

## Overview

A unified, dynamic notification service has been implemented across the entire application with Celery tasks for asynchronous processing, secure logging, and consistent phone number formatting.

## Key Features

### 1. Phone Number Format
- **Standard Format**: `91XXXXXXXXXX` (no + sign)
- **Kaleyra API Format**: `+91XXXXXXXXXX` (with + for API calls only)
- Automatic normalization from various input formats:
  - `9876543210` → `919876543210`
  - `+919876543210` → `919876543210`
  - `919876543210` → `919876543210`
  - `0919876543210` → `919876543210`
  - Numbers with spaces/dashes are also handled

### 2. Unified Notification Service
- **Location**: `portal/services/notification_service_v2.py`
- Single interface for all SMS and Email notifications
- Supports both async (Celery) and sync modes
- Automatic phone number normalization
- Secure logging with masked sensitive data

### 3. Celery Tasks
- **Location**: `portal/tasks/notification_tasks.py`
- `send_sms_task`: Send SMS via Kaleyra
- `send_email_task`: Send email via SMTP
- `send_otp_sms_task`: Send OTP via SMS
- Automatic retries with exponential backoff
- Secure logging with masked phone numbers and emails

### 4. Secure Logging
- Phone numbers masked: `9198****3210`
- Email addresses masked: `us***@example.com`
- OTP codes and sensitive data automatically redacted
- All notification operations logged with context

## Usage

### Send SMS
```python
from portal.services.notification_service_v2 import NotificationServiceV2

service = NotificationServiceV2()

# Async (default)
result = service.send_sms(
    phone_number='9876543210',  # Will be normalized to 919876543210
    message='Your message here',
    user_id=123,
    async_send=True
)

# Sync (for testing)
result = service.send_sms(
    phone_number='9876543210',
    message='Your message here',
    user_id=123,
    async_send=False
)
```

### Send Email
```python
from portal.services.notification_service_v2 import NotificationServiceV2

service = NotificationServiceV2()

# With template
result = service.send_email(
    to_email='user@example.com',
    subject='Welcome to Payswap',
    template_name='portal/emails/welcome.html',
    context={'user': user, 'verification_url': url},
    user_id=123,
    async_send=True
)

# Plain text
result = service.send_email(
    to_email='user@example.com',
    subject='Test Email',
    plain_message='This is a test email',
    user_id=123,
    async_send=True
)
```

### Send OTP
```python
from portal.services.otp_service import OTPService

otp_service = OTPService()
success, otp_code = otp_service.send_otp(
    phone_number='9876543210',
    user_id=123,
    async_send=True
)
```

## Implementation Locations

### Updated Files
1. **Phone Utilities** (`portal/utils/phone_utils.py`)
   - Updated to use `91XXXXXXXXXX` format (no +)
   - `normalize_phone_number()`: Normalizes to 91XXXXXXXXXX
   - `format_phone_for_kaleyra()`: Adds + for Kaleyra API

2. **Kaleyra Client** (`portal/services/vendors/kaleyra.py`)
   - Updated to use India-specific endpoint: `https://api.in.kaleyra.io/v1/<<SID>>/sms`
   - Phone normalization integrated
   - Proper error handling

3. **OTP Service** (`portal/services/otp_service.py`)
   - Now uses unified notification service
   - Supports async/sync modes
   - Secure logging integrated

4. **Views** (`portal/views.py`)
   - MFA setup: Uses unified OTP service
   - MFA verify: Uses unified OTP service
   - Password reset: Uses unified email service
   - All notifications sent asynchronously

5. **Celery Tasks** (`portal/tasks/notification_tasks.py`)
   - New file with notification tasks
   - Secure logging with masked data
   - Retry logic with exponential backoff

6. **Logging Helper** (`portal/utils/logging_helper.py`)
   - Added `sanitize_sensitive_data()` function
   - Masks phone numbers, emails, and sensitive data

## Testing

### Test Command
```bash
# Test SMS
python manage.py test_notifications --phone 9876543210 --sync

# Test Email
python manage.py test_notifications --email user@example.com --sync

# Test OTP
python manage.py test_notifications --phone 9876543210 --test-otp --sync

# Test with user ID
python manage.py test_notifications --user-id 1 --sync

# Test async (requires Celery worker)
python manage.py test_notifications --phone 9876543210 --email user@example.com
```

### Test Results
- Phone normalization: ✅ Working
- SMS sending: ✅ Working (via Kaleyra)
- Email sending: ✅ Working (via SMTP)
- OTP sending: ✅ Working
- Secure logging: ✅ Working (data masked)
- Celery tasks: ✅ Working (async mode)

## Security Features

1. **Phone Number Masking**: `9198****3210`
2. **Email Masking**: `us***@example.com`
3. **OTP Masking**: OTP codes never logged
4. **Sensitive Data**: Automatically redacted in logs
5. **Error Handling**: Errors logged without exposing sensitive data

## Celery Configuration

Ensure Celery worker is running:
```bash
celery -A core worker --loglevel=info
```

For development/testing, you can use `async_send=False` to send synchronously.

## Phone Number Format Summary

- **Internal Storage**: `91XXXXXXXXXX` (12 digits, no +)
- **Kaleyra API**: `+91XXXXXXXXXX` (added automatically)
- **Logging**: `9198****3210` (masked)

## Next Steps

1. ✅ Phone normalization updated to 91XXXXXXXXXX format
2. ✅ Unified notification service created
3. ✅ Celery tasks implemented
4. ✅ Secure logging integrated
5. ✅ All views updated to use new service
6. ✅ Test command created
7. ⏳ Production testing recommended

## Notes

- All notifications are sent asynchronously by default
- Use `async_send=False` for synchronous sending (testing only)
- Phone numbers are automatically normalized before sending
- All operations are logged securely with masked data
- Celery worker must be running for async notifications
