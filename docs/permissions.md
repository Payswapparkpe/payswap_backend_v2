# Permissions Documentation

## Overview

Portal uses Django Groups and Permissions for role-based access control.

## Roles

### B2B Roles
- **Admin**: Full access, highest hierarchy
- **Super**: High-level access
- **Employee**: Standard employee access
- **Distributor**: Distributor access
- **Retailer**: Retailer access

### B2C Roles
- **Customer**: Customer access
- **Vendor**: Vendor access

## Permission Management

### Default Permissions
Each role has default permissions assigned via Django Groups.

### Custom Permissions
Admins can:
- Assign permissions to individual users
- Revoke permissions from users
- Change user roles
- Modify role permissions

## Permission Checks

### In Views
Use custom permission classes:
```python
from portal.permissions import HasPermission

class MyView:
    permission_classes = [HasPermission('portal.view_user')]
```

### In Templates
Use template tags:
```django
{% if user|has_permission:'portal.view_user' %}
    <!-- Show content -->
{% endif %}
```

## Sidebar Menu

Menu items are shown based on user permissions. Each menu item checks for specific permission before rendering.
