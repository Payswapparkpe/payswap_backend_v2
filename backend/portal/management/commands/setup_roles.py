"""
Management command to setup default roles, groups, and permissions
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from portal.models import Role
from portal.utils.helpers import get_or_create_group


class Command(BaseCommand):
    help = 'Setup default roles, groups, and permissions'

    def handle(self, *args, **options):
        self.stdout.write('Setting up roles and groups...')
        
        # Define roles with hierarchy and MFA requirements (only these 7 types)
        roles_data = [
            {
                'name': 'Super Admin',
                'code': 'super_admin',
                'category': 'b2b',
                'hierarchy_level': 100,
                'mfa_required': True,
            },
            {
                'name': 'Admin',
                'code': 'admin',
                'category': 'b2b',
                'hierarchy_level': 90,
                'mfa_required': True,
            },
            {
                'name': 'Employee',
                'code': 'employee',
                'category': 'b2b',
                'hierarchy_level': 50,
                'mfa_required': True,
            },
            {
                'name': 'Super Distributor',
                'code': 'super_distributor',
                'category': 'b2b',
                'hierarchy_level': 45,
                'mfa_required': True,
            },
            {
                'name': 'Distributor',
                'code': 'distributor',
                'category': 'b2b',
                'hierarchy_level': 40,
                'mfa_required': True,
            },
            {
                'name': 'Retailer',
                'code': 'retailer',
                'category': 'b2b',
                'hierarchy_level': 30,
                'mfa_required': False,
            },
            {
                'name': 'Customer',
                'code': 'customer',
                'category': 'b2c',
                'hierarchy_level': 20,
                'mfa_required': False,
            },
            {
                'name': 'Fleet Admin',
                'code': 'fleet_admin',
                'category': 'b2b',
                'hierarchy_level': 55,
                'mfa_required': True,
            },
            {
                'name': 'Fleet Manager',
                'code': 'fleet_manager',
                'category': 'b2b',
                'hierarchy_level': 52,
                'mfa_required': False,
            },
            {
                'name': 'Fleet Operator',
                'code': 'fleet_operator',
                'category': 'b2b',
                'hierarchy_level': 48,
                'mfa_required': False,
            },
            {
                'name': 'Fleet Dispatcher',
                'code': 'fleet_dispatcher',
                'category': 'b2b',
                'hierarchy_level': 46,
                'mfa_required': False,
            },
        ]
        
        # Create roles
        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                code=role_data['code'],
                defaults={
                    'name': role_data['name'],
                    'category': role_data['category'],
                    'hierarchy_level': role_data['hierarchy_level'],
                    'mfa_required': role_data['mfa_required'],
                }
            )
            
            if not created:
                # Update existing role
                role.name = role_data['name']
                role.category = role_data['category']
                role.hierarchy_level = role_data['hierarchy_level']
                role.mfa_required = role_data['mfa_required']
                role.save()
            
            # Create Django Group for each role
            group_name = f"{role_data['name']} Group"
            group = get_or_create_group(group_name)
            
            # Define default permissions for each role
            role_permissions_map = {
                'super_admin': [
                    # Super Admin gets all permissions - set below
                ],
                'admin': [
                    'portal.view_profile', 'portal.add_profile', 'portal.change_profile',
                    'portal.view_user', 'portal.add_user', 'portal.change_user',
                    'portal.view_kyc', 'portal.change_kyc',
                    'portal.view_wallet', 'portal.view_wallettransaction',
                ],
                'employee': [
                    'portal.view_profile', 'portal.view_user',
                    'portal.view_kyc', 'portal.change_kyc',
                    'portal.view_wallet', 'portal.view_wallettransaction',
                ],
                'super_distributor': [
                    'portal.view_profile', 'portal.view_user',
                    'portal.view_wallet', 'portal.view_wallettransaction',
                ],
                'distributor': [
                    'portal.view_profile', 'portal.view_user',
                    'portal.view_wallet', 'portal.view_wallettransaction',
                ],
                'retailer': [
                    'portal.view_profile',
                    'portal.view_wallet', 'portal.view_wallettransaction',
                ],
                'customer': [
                    'portal.view_profile',
                    'portal.view_wallet', 'portal.view_wallettransaction',
                    'portal.add_kyc', 'portal.view_kyc',
                ],
                'fleet_admin': [
                    'portal.view_profile', 'portal.view_user',
                    'portal.view_kyc', 'portal.view_wallet', 'portal.view_wallettransaction',
                ],
                'fleet_manager': [
                    'portal.view_profile', 'portal.view_user',
                    'portal.view_wallet', 'portal.view_wallettransaction',
                ],
                'fleet_operator': [
                    'portal.view_profile',
                    'portal.view_wallet', 'portal.view_wallettransaction',
                ],
                'fleet_dispatcher': [
                    'portal.view_profile',
                    'portal.view_wallet', 'portal.view_wallettransaction',
                ],
            }
            
            # Assign permissions to Role.default_permissions and sync to Group
            # Only Super Admin gets ALL permissions; Admin gets department-wise roles via Hub RBAC from Super Admin
            if role_data['code'] == 'super_admin':
                all_permissions = Permission.objects.all()
                role.default_permissions.set(all_permissions)
                group.permissions.set(all_permissions)
            else:
                # Get permissions for this role
                perm_codenames = role_permissions_map.get(role_data['code'], [])
                permissions_to_add = []
                
                for perm_codename in perm_codenames:
                    try:
                        app_label, codename = perm_codename.split('.', 1)
                        permission = Permission.objects.filter(
                            content_type__app_label=app_label,
                            codename=codename
                        ).first()
                        if permission:
                            permissions_to_add.append(permission)
                    except Exception:
                        pass
                
                # Set permissions on Role.default_permissions
                if permissions_to_add:
                    role.default_permissions.set(permissions_to_add)
                
                # Sync to Group
                group.permissions.set(permissions_to_add)
            
            # Save role to ensure default_permissions are saved
            role.save()
            
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created/Updated role: {role.name} ({role.code}) with {group.permissions.count()} permissions')
            )
        
        self.stdout.write(self.style.SUCCESS('\nSuccessfully setup all roles and groups!'))
