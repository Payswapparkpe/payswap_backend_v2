# Createsuperuser Command Workaround

## Issue
Django's default `createsuperuser` command is being used instead of our custom command because Django's command discovery finds `django.contrib.auth` commands before `portal` commands (based on INSTALLED_APPS order).

When using Django's default command, it fails with:
```
CommandError: Role is required. All users must have a role.
```

## Solution Options

### Option 1: Use Non-Interactive Mode with All Fields
Since Django's default command doesn't know about our custom fields, you need to create the superuser through the Django shell or use our custom command directly:

```python
python manage.py shell
```

Then in the shell:
```python
from portal.models import User, Profile, Role
from portal.utils.user_utils import generate_username, get_role_prefix

# Get the admin role
role = Role.objects.get(code='admin')
role_prefix = get_role_prefix('admin')
username = generate_username(role_prefix)

# Create user
user = User.objects.create_user(
    username=username,
    password='YourSecurePassword123!',
    role_code='admin',
    role=role,
    is_staff=True,
    is_superuser=True,
    is_active=True,
    email_verified=True,
)

# Create profile
profile = Profile.objects.create(
    user=user,
    first_name='Admin',
    email='admin@payswap.in',
    phone='919876543210',
    type='individual',
    email_verified=True,
    phone_verified=True,
)

print(f"Superuser created: {user.username}")
```

### Option 2: Use Management Command Directly
You can call our custom command directly:

```python
python manage.py shell
```

Then:
```python
from portal.management.commands.createsuperuser import Command
from io import StringIO
import sys

# Create command instance
cmd = Command()
cmd.stdout = StringIO()

# Run with arguments
cmd.handle(
    first_name='Admin',
    phone='919876543210',
    email='admin@payswap.in',
    role_code='admin',
    password='YourSecurePassword123!',
    noinput=True
)
```

### Option 3: Create a Helper Script
Create a file `create_admin.py`:

```python
#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from portal.management.commands.createsuperuser import Command

cmd = Command()
cmd.handle(
    first_name='Admin',
    phone='919876543210',
    email='admin@payswap.in',
    role_code='admin',
    password='YourSecurePassword123!',
    noinput=True
)
```

Then run:
```bash
python create_admin.py
```

## Why This Happens
Django's command discovery works by:
1. Iterating through INSTALLED_APPS in order
2. Finding commands in each app's `management/commands` directory
3. The first command found with a given name is used

Since `django.contrib.auth` comes before `portal` in INSTALLED_APPS, Django finds the default `createsuperuser` first.

## Future Fix
To properly fix this, we would need to:
1. Move `portal` before `django.contrib.auth` in INSTALLED_APPS (not recommended - breaks Django admin)
2. Use a custom ManagementUtility class (complex)
3. Monkey-patch Django's command discovery (fragile)

For now, use one of the workarounds above.
