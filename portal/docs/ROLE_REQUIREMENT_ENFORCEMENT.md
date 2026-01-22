# Role Requirement Enforcement

## Overview

All users **must** have a role. This is enforced at multiple levels:
- Database level (non-nullable field)
- Model validation level
- Form validation level
- User creation methods

---

## ✅ Enforcement Levels

### 1. Database Level

**Field Definition:**
```python
role_code = models.CharField(
    max_length=20,
    choices=ROLE_CHOICES,
    blank=False,
    null=False,  # Cannot be NULL in database
    help_text="User role code (required)"
)
```

**Migration:**
- `0002_enforce_role_required.py` ensures:
  - Existing users without roles get assigned a default role (customer)
  - Database constraint prevents NULL values

### 2. Model Validation Level

**`clean()` Method:**
- Validates `role_code` is present
- Validates `role_code` is a valid choice
- Ensures Role object exists for the role_code
- Auto-sets Role ForeignKey from role_code

**`save()` Method:**
- Validates role_code is set before saving
- Ensures Role object is set
- Raises ValidationError if role_code is missing

### 3. User Creation Methods

**`create_user()` Class Method:**
- Requires `role_code` in extra_fields
- Raises ValidationError if role_code is missing
- Auto-sets Role ForeignKey
- Auto-generates username based on role

**Direct User() Instantiation:**
- `clean()` method validates role_code
- `save()` method enforces role requirement

### 4. Form Validation Level

**All Forms:**
- `SignUpForm`: role_code is required
- `UserCreateForm`: role_code is required with custom error message
- Custom error message: "Please select a role for the user."

### 5. Admin Interface

**UserAdmin:**
- `add_fieldsets` includes role_code as required
- Description: "All fields are required. Role is mandatory for all users."

### 6. Management Commands

**`createsuperuser`:**
- Requires `--role` argument (defaults to 'admin')
- Validates role exists before creating user
- Sets role_code and role automatically

**`seed_data`:**
- All users created with role_code specified
- No users created without roles

---

## 🔒 Validation Flow

### When Creating a User:

1. **Form Validation** → Checks role_code is provided
2. **Model clean()** → Validates role_code exists and is valid
3. **Model save()** → Ensures role_code is set, sets Role object
4. **Database** → Rejects NULL values (constraint)

### Error Messages:

- **Form Level**: "Please select a role for the user."
- **Model Level**: "Role is required. All users must have a role."
- **Invalid Role**: "Role with code 'X' does not exist. Please run 'python manage.py setup_roles' first."

---

## 📋 Available Roles

All users must have one of these roles:

1. **admin** - Admin (B2B, hierarchy: 100)
2. **super** - Super (B2B, hierarchy: 90)
3. **employee** - Employee (B2B, hierarchy: 50)
4. **distributor** - Distributor (B2B, hierarchy: 40)
5. **retailer** - Retailer (B2B, hierarchy: 30)
6. **customer** - Customer (B2C, hierarchy: 20)
7. **vendor** - Vendor (B2C, hierarchy: 10)

---

## 🚨 What Happens if Role is Missing?

### During User Creation:
- **Form**: Shows error "Please select a role for the user."
- **Model**: Raises ValidationError "Role is required. All users must have a role."
- **Database**: Rejects the save operation

### For Existing Users (Migration):
- Migration `0002_enforce_role_required` assigns default role (customer)
- Then enforces non-nullable constraint

---

## ✅ Verification

### Check All Users Have Roles:
```python
from portal.models import User

# All users should have role_code
users_without_role = User.objects.filter(
    Q(role_code__isnull=True) | Q(role_code='')
)
print(f'Users without role: {users_without_role.count()}')  # Should be 0
```

### Test Role Requirement:
```python
from portal.models import User
from django.core.exceptions import ValidationError

# This should raise ValidationError
try:
    user = User(
        first_name='Test',
        email='test@example.com',
        phone='+919876543210'
        # Missing role_code
    )
    user.full_clean()  # Will raise ValidationError
except ValidationError as e:
    print('Role is required:', e.message_dict['role_code'])
```

---

## 📝 Migration Applied

**Migration:** `0002_enforce_role_required`
- ✅ Assigned default role to 1 existing user without role
- ✅ Made role_code non-nullable in database
- ✅ All users now have roles

**Result:**
- Total users: 10
- Users without role: 0 ✅

---

## 🎯 Summary

**All users must have a role** - This is enforced at:
1. ✅ Database level (non-nullable)
2. ✅ Model validation (clean/save methods)
3. ✅ Form validation (required fields)
4. ✅ User creation methods (create_user)
5. ✅ Admin interface (required field)
6. ✅ Management commands (createsuperuser)

**No user can be created or saved without a role.**
