# API Integrations Documentation

## Overview

Portal integrates with multiple external services for document verification, OTP, email, notifications, and file storage.

## Document Verification

### Vendors
- **Cashfree**: KYC document verification
- **Invincible Ocean**: Alternative KYC verification

### Usage
```python
from portal.services.document_verification import DocumentVerificationService

service = DocumentVerificationService()
result = service.verify('aadhaar', '123456789012', '/path/to/file.pdf')
```

### Failover
If primary vendor fails, system automatically tries secondary vendor.

## OTP Service (Kaleyra)

### Usage
```python
from portal.services.otp_service import OTPService

otp_service = OTPService()
success, message = otp_service.send_otp('+919876543210')
verified = otp_service.verify_otp('+919876543210', '123456')
```

### Rate Limiting
- Max 3 OTP requests per 10 minutes per phone number
- OTP expires in 5 minutes

## Email Service (AWS SES)

### Usage
```python
from portal.services.notification_service import NotificationService

service = NotificationService()
service.send_email(
    'user@example.com',
    'Welcome',
    'portal/emails/welcome.html',
    {'user': user}
)
```

## Notification Service (AWS SNS)

### Usage
```python
service.send_notification(user, 'sms', 'Your transaction is complete')
service.send_notification(user, 'email', 'Account updated')
```

## Storage Service (AWS S3)

### Usage
```python
from portal.services.storage_service import StorageService

storage = StorageService()
url = storage.upload_kyc_document(user_id, 'aadhaar', uploaded_file)
signed_url = storage.get_signed_url(url, expiry_hours=1)
```

### File Organization
- KYC: `kyc/{user_id}/{document_type}/{filename}`
- Profiles: `profiles/{profile_id}/{filename}`
