# Role and Permissions Implementation

## Overview

This document describes the comprehensive role-based access control (RBAC) system implemented in the Portal app, using Django Groups and Permissions with automatic synchronization.

## Key Features

### 1. **Automatic Django Group Synchronization**
- Users are automatically added to Django Groups based on their Role
- When a user's role changes, they are automatically moved to the appropriate group
- Role permissions are automatically synced to Django Groups

### 2. **Role-Based Permissions**
- Each Role has `default_permissions` (ManyToManyField to Permission)
- Permissions assigned to Role are automatically synced to the corresponding Django Group
- Users inherit permissions from their role's group

### 3. **Permission Management**
- Assign/revoke permissions directly to users
- Assign/revoke permissions to roles (affects all users with that role)
- Change user roles with automatic group synchronization
- View all permissions for users and roles

### 4. **User Roles**

#### B2B Roles (Higher Hierarchy)
- **Admin** (hierarchy: 100, MFA: Required)
  - All permissions
  - Can manage all users, roles, and permissions
  
- **Super** (hierarchy: 90, MFA: Required)
  - Profile management
  - User management
  - KYC management
  - Wallet viewing
  
- **Employee** (hierarchy: 50, MFA: Required)
  - View profiles and users
  - Manage KYC
  - View wallets and transactions
  
- **Distributor** (hierarchy: 40, MFA: Required)
  - View profiles and users
  - View wallets and transactions
  
- **Retailer** (hierarchy: 30, MFA: Not Required)
  - View profile
  - View wallet and transactions

#### B2C Roles (Lower Hierarchy)
- **Customer** (hierarchy: 20, MFA: Not Required)
  - View profile
  - View wallet and transactions
  - Submit and view KYC
  
- **Vendor** (hierarchy: 10, MFA: Not Required)
  - View profile
  - View wallet and transactions
  - Submit and view KYC

## Implementation Details

### Signals (`portal/signals.py`)

Three signals handle automatic synchronization:

1. **`sync_user_to_groups_on_save`**
   - Triggered when User is saved
   - Syncs user to appropriate Django Group based on role

2. **`sync_role_permissions_to_group_on_save`**
   - Triggered when Role is saved
   - Syncs Role.default_permissions to Django Group permissions

3. **`sync_role_permissions_to_group_on_m2m_change`**
   - Triggered when permissions are added/removed from Role.default_permissions
   - Updates Django Group permissions accordingly

### Role Utilities (`portal/utils/role_utils.py`)

Key functions:

- `sync_user_to_groups(user, role)`: Sync user to Django Groups
- `sync_role_permissions_to_group(role)`: Sync role permissions to group
- `assign_role_to_user(user, role)`: Assign role and sync to groups
- `change_user_role(user, new_role_code)`: Change user role
- `assign_permission_to_user(user, permission)`: Assign permission directly to user
- `revoke_permission_from_user(user, permission)`: Revoke permission from user
- `assign_permission_to_role(role, permission)`: Assign permission to role (affects all users)
- `revoke_permission_from_role(role, permission)`: Revoke permission from role
- `get_user_permissions(user)`: Get all permissions for user (groups + direct)

### User Model Enhancements

The `User.save()` method now:
1. Auto-generates username if not set (format: `[RolePrefix]00[6 digits]`)
2. Sets role from role_code if role is not set
3. Automatically syncs user to Django Groups after save

### Setup Roles Command

The `setup_roles` management command:
- Creates all default roles with hierarchy and MFA requirements
- Creates Django Groups for each role
- Assigns default permissions to roles
- Syncs permissions to Django Groups

**Run it with:**
```bash
python manage.py setup_roles
```

## Usage

### Assign Permission to User

```python
from portal.utils.role_utils import assign_permission_to_user
from django.contrib.auth.models import Permission

permission = Permission.objects.get(codename='view_user', content_type__app_label='portal')
assign_permission_to_user(user, permission)
```

### Revoke Permission from User

```python
from portal.utils.role_utils import revoke_permission_from_user

revoke_permission_from_user(user, permission)
```

### Change User Role

```python
from portal.utils.role_utils import change_user_role

change_user_role(user, 'employee')  # Changes role to employee
```

### Assign Permission to Role

```python
from portal.utils.role_utils import assign_permission_to_role

assign_permission_to_role(role, permission)  # All users with this role get the permission
```

### Check User Permissions

```python
from portal.utils.role_utils import get_user_permissions

all_permissions = get_user_permissions(user)
```

## Web Interface

### Permission Management Page (`/permissions/`)

Accessible only to Admin users. Features:

1. **User Permissions Section**
   - Assign permission to user
   - View all users with their roles and permissions
   - Change user role (with modal)

2. **Role Permissions Section**
   - Assign permission to role
   - View all roles with their default permissions
   - Revoke permission from role (one-click)

## Sidebar Menu

The sidebar menu (`portal/templates/portal/partials/sidebar_menu.html`) uses permission checks to show/hide menu items:

```django
{% if user|has_permission:'portal.view_user' %}
    <li>
        <a href="/users/">Users</a>
    </li>
{% endif %}
```

## Login Flow

1. User enters **username** and **password**
2. System verifies:
   - User is active
   - Email is verified
   - MFA is configured (if role requires it)
   - KYC is completed (if role requires it)
3. If MFA required:
   - User enters **OTP** (SMS) or **Authenticator code**
4. On success, user is redirected to role-specific dashboard

## Dashboard Routing

Users are automatically redirected to their role-specific dashboard:
- `/dashboard/admin/` - Admin dashboard
- `/dashboard/employee/` - Employee dashboard
- `/dashboard/super/` - Super dashboard
- `/dashboard/distributor/` - Distributor dashboard
- `/dashboard/retailer/` - Retailer dashboard
- `/dashboard/customer/` - Customer dashboard
- `/dashboard/vendor/` - Vendor dashboard

## Security Features

1. **Automatic Group Sync**: Users are always in the correct Django Group
2. **Permission Inheritance**: Users get permissions from their role's group
3. **Direct Permissions**: Can assign permissions directly to users (overrides group)
4. **Audit Logging**: All permission/role changes are logged
5. **MFA Enforcement**: High-privilege roles require MFA
6. **KYC Requirements**: Customer/Vendor roles require KYC completion

## Best Practices

1. **Use Role Permissions**: Assign permissions to roles, not individual users
2. **Run setup_roles**: After migrations, run `python manage.py setup_roles`
3. **Check Permissions**: Use `user.has_perm('portal.view_user')` in views
4. **Template Tags**: Use `{% if user|has_permission:'portal.view_user' %}` in templates
5. **Permission Classes**: Use DRF permission classes for API views

## Troubleshooting

### User not getting permissions
1. Check if user has a role assigned
2. Check if role has default_permissions set
3. Check if user is in the correct Django Group
4. Run `python manage.py setup_roles` to sync

### Permissions not syncing
1. Check signals are registered (check `portal/apps.py`)
2. Verify `portal.signals` is imported in `apps.py`
3. Check Django Groups exist for roles
4. Manually sync: `sync_user_to_groups(user, user.role)`

### Role changes not taking effect
1. User must be saved after role change
2. Signals should automatically sync groups
3. Check user.groups.all() to verify group membership

## Files Modified/Created

### New Files
- `portal/signals.py` - Django signals for auto-sync
- `portal/utils/role_utils.py` - Role and permission utilities
- `portal/docs/ROLE_PERMISSIONS_IMPLEMENTATION.md` - This document

### Modified Files
- `portal/models.py` - User.save() enhanced
- `portal/apps.py` - Signal registration
- `portal/views.py` - Enhanced permission management views
- `portal/urls.py` - Added permission management routes
- `portal/management/commands/setup_roles.py` - Enhanced with permission sync
- `portal/templates/portal/permissions/manage.html` - Comprehensive UI
- `portal/templatetags/portal_tags.py` - Added get_item filter

## Next Steps

1. Run migrations: `python manage.py migrate`
2. Setup roles: `python manage.py setup_roles`
3. Create admin user: `python manage.py createsuperuser`
4. Test permission management at `/permissions/`
5. Verify sidebar menu shows correct items based on permissions
