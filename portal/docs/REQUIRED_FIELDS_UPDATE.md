# Required Fields Update

## Overview

All user creation methods (including superuser creation) now require the following fields:
- **First Name** (required)
- **Mobile/Phone** (required)
- **Email** (required)
- **Username** (required, but can be auto-generated)
- **Role** (required)

## Changes Made

### 1. User Model (`portal/models.py`)

**Updated Fields:**
- `first_name`: Now required (blank=False)
- `email`: Now required (blank=False)
- `phone`: Now required (blank=False)
- `role_code`: Now required (blank=False)
- `username`: Can be provided or auto-generated

**Validation:**
- Added `clean()` method to validate all required fields
- Username is auto-generated if not provided (format: `[Role]00[6 digits]`)

### 2. Custom Createsuperuser Command (`portal/management/commands/createsuperuser.py`)

**New Command:** Custom `createsuperuser` command that requires all fields

**Usage:**

**Interactive Mode:**
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

**Non-Interactive Mode:**
```bash
python manage.py createsuperuser \
    --first_name "John" \
    --phone "+919876543210" \
    --email "admin@payswap.in" \
    --username "A00123456" \
    --role admin \
    --password "SecurePassword123" \
    --noinput
```

**Available Roles:**
- admin
- super
- employee
- distributor
- retailer
- customer
- vendor

### 3. User Creation Form (`portal/forms.py`)

**UserCreateForm Updates:**
- Added `first_name` field (required)
- Added `phone` field (required)
- Added `username` field (optional, auto-generated if not provided)
- All fields now properly validated

**SignUpForm Updates:**
- Added `first_name` field (required)
- Phone field already existed, now properly required
- Email and role_code already existed, now properly required

### 4. Admin Interface (`portal/admin.py`)

**UserAdmin Updates:**
- Added "Required Information" fieldset with: first_name, email, phone, username, role_code
- Updated `add_fieldsets` to include all required fields
- Updated `list_display` to show first_name and phone
- Updated `search_fields` to include first_name and phone

### 5. Views (`portal/views.py`)

**SignUpView:**
- Updated to pass `first_name` when creating users

**UserCreateView:**
- Updated to pass `first_name`, `phone`, and `username` when creating users

### 6. Seed Data Command (`portal/management/commands/seed_data.py`)

**Updated all User creations to include:**
- `first_name`
- `phone`

## Migration Required

You need to create and run a migration for these changes:

```bash
python manage.py makemigrations portal
python manage.py migrate
```

**Note:** If you have existing users without these fields, you'll need to:
1. Create a data migration to populate missing fields
2. Or manually update existing users before running the migration

## Examples

### Creating a Superuser

**Interactive:**
```bash
$ python manage.py createsuperuser
First name: John
Mobile number: +919876543210
Email address: admin@payswap.in
Username (leave blank for auto-generation): 
Auto-generated username: A00786543
Role [admin]: admin
Password: 
Password (again): 
Superuser created successfully!
  Username: A00786543
  Email: admin@payswap.in
  Role: admin
  First Name: John
  Phone: +919876543210
```

**Non-Interactive:**
```bash
python manage.py createsuperuser \
    --first_name "John Doe" \
    --phone "+919876543210" \
    --email "john@example.com" \
    --role admin \
    --password "SecurePass123" \
    --noinput
```

### Creating a User via Admin Interface

1. Go to `/admin/portal/user/add/`
2. Fill in all required fields:
   - First Name: Required
   - Email: Required
   - Phone: Required
   - Username: Optional (auto-generated if blank)
   - Role Code: Required
   - Password: Required
3. Save

### Creating a User via Web Form

1. Go to `/users/create/` (Admin only)
2. Fill in the form:
   - First Name: Required
   - Email: Required
   - Mobile Number: Required
   - Username: Optional (auto-generated if blank)
   - Role: Required
   - Password: Required
   - Confirm Password: Required
3. Submit

### Self-Onboarding (Sign Up)

1. Go to `/signup/`
2. Fill in the form:
   - First Name: Required
   - Email: Required
   - Mobile Number: Required
   - Role: Customer or Retailer only
   - Password: Required
   - Confirm Password: Required
3. Submit (username will be auto-generated)

## Validation

All required fields are validated:
- **First Name**: Must not be empty
- **Email**: Must be valid email format and not empty
- **Phone**: Must be valid phone number format and not empty
- **Role Code**: Must be one of the valid role choices
- **Username**: Must be unique (auto-generated if not provided)

## Backward Compatibility

⚠️ **Breaking Change**: Existing code that creates users without these fields will fail. Update all user creation code to include:
- `first_name`
- `phone`
- `email` (already required by Django)
- `role_code`

## Testing

After making these changes, test:
1. ✅ Creating superuser via command
2. ✅ Creating user via admin interface
3. ✅ Creating user via web form
4. ✅ Self-onboarding (sign up)
5. ✅ Username auto-generation
6. ✅ Validation errors for missing fields

## Files Modified

- `portal/models.py` - User model fields and validation
- `portal/management/commands/createsuperuser.py` - New custom command
- `portal/forms.py` - UserCreateForm and SignUpForm
- `portal/views.py` - SignUpView and UserCreateView
- `portal/admin.py` - UserAdmin configuration
- `portal/management/commands/seed_data.py` - Updated seed data creation
