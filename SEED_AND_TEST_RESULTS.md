# Seed Data and Test Results

## Seed Data Command

### Command
```bash
python manage.py seed_data
```

### What It Does
1. **Deletes all existing data** (Users, Profiles, Wallets, Transactions, KYC, UserPermissions)
2. **Sets up roles and groups** (calls setup_roles)
3. **Creates fresh seed data**:
   - 1 Admin user
   - 1 Super user
   - 1 Employee user
   - 1 Distributor user
   - 1 Retailer user
   - 3 Customer users
   - 1 Vendor user
   - Wallets for all users
   - Sample wallet transactions
   - Sample KYC records

### Seed Data Summary
- **Roles**: 7
- **Profiles**: 9
- **Users**: 9
- **Wallets**: 9
- **Wallet Transactions**: 2
- **KYC Records**: 2

### Test User Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | A00259150 | Admin@123 |
| Super | S00654348 | Super@123 |
| Employee | E00713429 | Employee@123 |
| Distributor | D00730570 | Distributor@123 |
| Retailer | R00965829 | Retailer@123 |
| Customer 1 | C00742941 | Customer@123 |
| Customer 2 | C00412552 | Customer@123 |
| Customer 3 | C00561007 | Customer@123 |
| Vendor | V00721283 | Vendor@123 |

## Test Results

### ✅ All Tests Passed

1. **Models Test**: ✓ PASSED
   - Role, Profile, User, Wallet models work correctly
   - Relationships are properly configured

2. **Authentication Test**: ✓ PASSED
   - User authentication works
   - Password verification works
   - User methods (requires_mfa, can_login) work

3. **Username Generation Test**: ✓ PASSED
   - Username format: [Role]00[6 digits]
   - All usernames are unique
   - Role prefixes are correct

4. **Encryption Test**: ✓ PASSED
   - Data encryption works
   - Data decryption works
   - Encrypted data is different from original

5. **MFA Utilities Test**: ✓ PASSED
   - TOTP secret generation works
   - TOTP verification works
   - Invalid codes are rejected

6. **Permissions Test**: ✓ PASSED
   - Permission checking works
   - Role-based permissions work

7. **Logging Test**: ✓ PASSED
   - Logging helper works
   - Sensitive data sanitization works
   - User action logging works

8. **HTTP Endpoints Test**: ✓ PASSED
   - Landing page: 200 OK
   - Sign in page: 200 OK
   - Sign up page: 200 OK
   - Dashboard redirects correctly

9. **Wallet Operations Test**: ✓ PASSED
   - Wallet creation works
   - Transaction creation works
   - Balance updates work
   - Decimal precision maintained

10. **KYC Operations Test**: ✓ PASSED
    - KYC creation works
    - KYC approval works
    - User KYC status updates work

## Manual Testing Guide

### 1. Test Landing Page
```bash
curl http://127.0.0.1:8000/
```
- Should return 200 OK
- Should show Payswap landing page

### 2. Test Sign In
1. Visit http://127.0.0.1:8000/signin/
2. Use credentials: `A00259150` / `Admin@123`
3. Should redirect to dashboard or MFA setup

### 3. Test Sign Up
1. Visit http://127.0.0.1:8000/signup/
2. Fill form with Customer or Retailer role
3. Should create new user and redirect to sign in

### 4. Test Dashboard
1. Sign in as any user
2. Visit http://127.0.0.1:8000/dashboard/
3. Should redirect to role-specific dashboard

### 5. Test User Management (Admin only)
1. Sign in as Admin
2. Visit http://127.0.0.1:8000/users/
3. Should see list of users
4. Can create new users

### 6. Test Wallet
1. Sign in as any user
2. Visit http://127.0.0.1:8000/wallet/
3. Should see wallet balance
4. View transactions

### 7. Test KYC Submission
1. Sign in as Customer
2. Visit http://127.0.0.1:8000/kyc/submit/
3. Submit KYC documents
4. Should create KYC record

## Database State After Seeding

All tables are populated with fresh data:
- ✅ Roles configured
- ✅ Groups created with permissions
- ✅ Users created with proper roles
- ✅ Profiles linked to users
- ✅ Wallets created for all users
- ✅ Sample transactions created
- ✅ Sample KYC records created

## Reset and Re-seed

To reset everything and create fresh data:
```bash
python manage.py seed_data
```

This will:
1. Delete all existing data
2. Recreate roles and groups
3. Create fresh seed data

## Notes

- All usernames are auto-generated in format: [Role]00[6 digits]
- All passwords follow pattern: [Role]@123
- Wallets are created automatically for all users
- MFA is enforced for Admin, Employee, Super, Distributor roles
- KYC is required for certain roles (configurable)
