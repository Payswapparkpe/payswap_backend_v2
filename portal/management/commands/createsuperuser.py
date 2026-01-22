"""
Custom createsuperuser command with required fields: first_name, phone, email, username, role
"""
from django.core.management.base import CommandError
from django.contrib.auth.management.commands.createsuperuser import Command as BaseCommand
from portal.models import User, Role
from portal.utils.user_utils import generate_username, get_role_prefix


class Command(BaseCommand):
    help = 'Create a superuser with first_name, mobile, email, username, and role'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--first_name',
            dest='first_name',
            help='User\'s first name (required)',
        )
        parser.add_argument(
            '--phone',
            dest='phone',
            help='User\'s mobile number (required)',
        )
        parser.add_argument(
            '--email',
            dest='email',
            help='User\'s email address (required)',
        )
        parser.add_argument(
            '--username',
            dest='username',
            help='Username (auto-generated if not provided)',
        )
        parser.add_argument(
            '--role',
            dest='role_code',
            choices=['admin', 'super', 'employee', 'distributor', 'retailer', 'customer', 'vendor'],
            default='admin',
            help='User role (default: admin)',
        )
        parser.add_argument(
            '--noinput',
            action='store_true',
            dest='noinput',
            help='Do not prompt for input (requires all fields via arguments)',
        )

    def handle(self, *args, **options):
        # Get required fields
        first_name = options.get('first_name')
        phone = options.get('phone')
        email = options.get('email')
        username = options.get('username')
        role_code = options.get('role_code', 'admin')
        noinput = options.get('noinput', False)

        # Interactive mode
        if not noinput:
            # Get first_name
            if not first_name:
                first_name = self._get_input('First name: ')
            
            # Get phone
            if not phone:
                phone = self._get_input('Mobile number: ')
            
            # Get email
            if not email:
                email = self._get_input('Email address: ')
            
            # Get username (optional, will be auto-generated)
            if not username:
                username = self._get_input('Username (leave blank for auto-generation): ')
                if not username.strip():
                    username = None
            
            # Get role
            if not role_code:
                self.stdout.write('Available roles: admin, super, employee, distributor, retailer, customer, vendor')
                role_code = self._get_input('Role [admin]: ') or 'admin'
        
        # Validate required fields
        if not first_name:
            raise CommandError('First name is required.')
        if not phone:
            raise CommandError('Mobile number is required.')
        if not email:
            raise CommandError('Email address is required.')
        if not role_code:
            raise CommandError('Role is required.')
        
        # Get or create role
        try:
            role = Role.objects.get(code=role_code)
        except Role.DoesNotExist:
            raise CommandError(f'Role with code "{role_code}" does not exist. Run "python manage.py setup_roles" first.')
        
        # Auto-generate username if not provided
        if not username:
            role_prefix = get_role_prefix(role_code)
            username = generate_username(role_prefix)
            self.stdout.write(self.style.WARNING(f'Auto-generated username: {username}'))
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            raise CommandError(f'Username "{username}" already exists.')
        
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            raise CommandError(f'Email "{email}" already exists.')
        
        # Get password
        password = options.get('password')
        if not password and not noinput:
            password = self._get_password()
        elif not password:
            raise CommandError('Password is required. Use --password or run in interactive mode.')
        
        # Create superuser
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                phone=phone,
                role_code=role_code,
                role=role,
                is_staff=True,
                is_superuser=True,
                is_active=True,
                email_verified=True,  # Auto-verify for superuser
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'Superuser created successfully!\n'
                                 f'  Username: {user.username}\n'
                                 f'  Email: {user.email}\n'
                                 f'  Role: {user.role_code}\n'
                                 f'  First Name: {user.first_name}\n'
                                 f'  Phone: {user.phone}')
            )
        except Exception as e:
            raise CommandError(f'Error creating superuser: {str(e)}')
    
    def _get_input(self, prompt):
        """Get input from user"""
        return input(prompt).strip()
    
    def _get_password(self):
        """Get password from user (with confirmation)"""
        import getpass
        
        password = getpass.getpass('Password: ')
        password_confirm = getpass.getpass('Password (again): ')
        
        if password != password_confirm:
            raise CommandError('Passwords do not match.')
        
        if len(password) < 8:
            raise CommandError('Password must be at least 8 characters long.')
        
        return password
