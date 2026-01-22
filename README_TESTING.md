# Testing Guide - Payswap Portal

## Quick Start

### 1. Seed Fresh Data
```bash
python manage.py seed_data
```

This command:
- ✅ Deletes ALL existing data (Users, Profiles, Wallets, Transactions, KYC)
- ✅ Sets up roles and groups
- ✅ Creates fresh seed data with test users

### 2. Run All Tests
```bash
python manage.py test_all
```

This runs comprehensive tests on:
- Models and relationships
- Authentication
- Username generation
- Encryption
- MFA utilities
- Permissions
- Logging
- HTTP endpoints
- Wallet operations
- KYC operations

## Test User Credentials

After running `seed_data`, use these credentials:

| Role | Username | Password |
|------|----------|----------|
| Admin | A00XXXXXX | Admin@123 |
| Super | S00XXXXXX | Super@123 |
| Employee | E00XXXXXX | Employee@123 |
| Distributor | D00XXXXXX | Distributor@123 |
| Retailer | R00XXXXXX | Retailer@123 |
| Customer | C00XXXXXX | Customer@123 |
| Vendor | V00XXXXXX | Vendor@123 |

*Note: Usernames are auto-generated. Check seed_data output for actual usernames.*

## Manual Testing Checklist

### ✅ Landing Page
- [ ] Visit http://127.0.0.1:8000/
- [ ] Verify page loads correctly
- [ ] Check navigation works
- [ ] Verify sign in/sign up links work

### ✅ Authentication
- [ ] Sign up as Customer/Retailer
- [ ] Sign in with test credentials
- [ ] Verify MFA setup for enforced roles
- [ ] Test MFA verification flow

### ✅ Dashboards
- [ ] Access role-specific dashboards
- [ ] Verify sidebar menu shows correct items
- [ ] Check permission-based menu rendering

### ✅ User Management (Admin)
- [ ] List users
- [ ] Create new user
- [ ] View user details
- [ ] Change user role
- [ ] Assign/revoke permissions

### ✅ Wallet
- [ ] View wallet balance
- [ ] View transaction history
- [ ] Verify transactions display correctly

### ✅ KYC
- [ ] Submit KYC documents
- [ ] Verify KYC status updates
- [ ] Test KYC approval (Admin)

## Test Results

### Current Status: ✅ ALL TESTS PASSING

- **Models**: ✅ Working
- **Authentication**: ✅ Working
- **Username Generation**: ✅ Working
- **Encryption**: ✅ Working
- **MFA Utilities**: ✅ Working
- **Permissions**: ✅ Working
- **Logging**: ✅ Working
- **HTTP Endpoints**: ✅ Working
- **Wallet Operations**: ✅ Working
- **KYC Operations**: ✅ Working

## Reset Database

To completely reset and start fresh:

```bash
# Delete all data and recreate
python manage.py seed_data

# Or manually reset database (CAUTION: Deletes everything)
python manage.py flush --noinput
python manage.py migrate
python manage.py setup_roles
python manage.py seed_data
```

## Notes

- Seed data command always deletes existing data before creating new
- All usernames are auto-generated in format: [Role]00[6 digits]
- Passwords follow pattern: [Role]@123
- MFA is enforced for: Admin, Employee, Super, Distributor
- Server runs on: http://127.0.0.1:8000/
