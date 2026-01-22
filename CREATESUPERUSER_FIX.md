# Createsuperuser Command Fix

## Issue
Django's default `createsuperuser` command was failing with:
```
django.core.exceptions.FieldDoesNotExist: User has no field named 'email'
```

## Root Cause
1. The User model had `email` defined as a property (reading from Profile) but not as a database field
2. Django's default `createsuperuser` command tries to access the email field during argument parsing
3. Our custom command wasn't being used because Django's command discovery finds `django.contrib.auth` commands first

## Solution
1. **Added email field to User model**: `email = models.EmailField(blank=True, null=True)` for Django compatibility
2. **Kept email property**: The `@property` method still reads from Profile, but the field exists for Django's commands
3. **Updated custom createsuperuser command**: Changed to inherit from `BaseCommand` instead of Django's default to avoid conflicts
4. **Set REQUIRED_FIELDS = []**: This tells Django not to prompt for email in the default command

## Usage

### Interactive Mode
```bash
python manage.py createsuperuser
```
Prompts for:
- First name
- Mobile number
- Email address
- Username (optional, auto-generated if blank)
- Role (default: admin)
- Password

### Non-Interactive Mode
```bash
python manage.py createsuperuser \
    --first_name "John" \
    --phone "9876543210" \
    --email "admin@payswap.in" \
    --username "A00123456" \
    --role admin \
    --password "SecurePassword123" \
    --noinput
```

## Notes
- The email field exists in the User model for Django compatibility
- The email property reads from Profile when available
- Our custom command creates both User and Profile instances
- Email and phone are stored in Profile, not User model
