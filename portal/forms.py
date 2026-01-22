"""
Django forms for portal app
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from portal.models import User, Profile, KYC
from portal.utils.validators import validate_phone_number


class MultipleFileInput(forms.Widget):
    """Custom widget for multiple file uploads"""
    input_type = 'file'
    needs_multipart_form = True
    template_name = 'django/forms/widgets/file.html'
    
    def __init__(self, attrs=None):
        if attrs is None:
            attrs = {}
        attrs['multiple'] = True
        super().__init__(attrs)
    
    def value_from_datadict(self, data, files, name):
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        value = files.get(name)
        if value:
            return [value]
        return []


class SignUpForm(forms.ModelForm):
    """Sign up form for self-onboarding (Customer/Retailer)"""
    
    first_name = forms.CharField(
        label='First Name',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter your first name'
        })
    )
    
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Create a password'
        }),
        min_length=8
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Confirm your password'
        })
    )
    role_code = forms.ChoiceField(
        choices=[('customer', 'Customer'), ('retailer', 'Retailer')],
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
        })
    )
    
    class Meta:
        model = User
        fields = ['first_name', 'email', 'phone']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
                'placeholder': 'Enter your email'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
                'placeholder': 'Enter your mobile number'
            }),
        }
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            validate_phone_number(phone)
        return phone


class SignInForm(forms.Form):
    """Sign in form"""
    
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter your username',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter your password'
        })
    )
    remember = forms.BooleanField(required=False)


class MFASetupForm(forms.Form):
    """MFA setup form"""
    
    mfa_method = forms.ChoiceField(
        choices=[('otp', 'OTP (SMS)'), ('authenticator', 'Authenticator App')],
        widget=forms.RadioSelect(attrs={
            'class': 'mr-3'
        })
    )
    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter your phone number'
        })
    )
    totp_code = forms.CharField(
        required=False,
        max_length=6,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': '000000'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        mfa_method = cleaned_data.get('mfa_method')
        phone = cleaned_data.get('phone')
        totp_code = cleaned_data.get('totp_code')
        
        if mfa_method == 'otp' and not phone:
            raise forms.ValidationError("Phone number is required for OTP method")
        
        if mfa_method == 'authenticator' and not totp_code:
            raise forms.ValidationError("Verification code is required for Authenticator method")
        
        return cleaned_data


class MFAVerifyForm(forms.Form):
    """MFA verification form"""
    
    mfa_code = forms.CharField(
        max_length=6,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20 text-center text-2xl tracking-widest',
            'placeholder': '000000',
            'autofocus': True
        })
    )


class ProfileCreateForm(forms.ModelForm):
    """Profile creation form"""
    
    class Meta:
        model = Profile
        fields = ['name', 'type', 'business_name', 'tax_id', 'phone', 'email', 'address']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'business_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'tax_id': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
                'rows': 3
            }),
        }
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            validate_phone_number(phone)
        return phone


class UserCreateForm(forms.ModelForm):
    """User creation form (for Admin)"""
    
    first_name = forms.CharField(
        label='First Name',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter first name'
        })
    )
    
    phone = forms.CharField(
        label='Mobile Number',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter mobile number'
        }),
        validators=[validate_phone_number]
    )
    
    username = forms.CharField(
        label='Username',
        required=False,
        help_text='Leave blank to auto-generate',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Auto-generated if not provided'
        })
    )
    
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
        }),
        min_length=8
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
        })
    )
    
    class Meta:
        model = User
        fields = ['first_name', 'email', 'phone', 'username', 'role_code', 'profile']
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
                'placeholder': 'Enter email address'
            }),
            'role_code': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'profile': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
        }
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            validate_phone_number(phone)
        return phone


class KYCSubmitForm(forms.Form):
    """KYC submission form"""
    
    document_type = forms.ChoiceField(
        choices=[
            ('aadhaar', 'Aadhaar'),
            ('pan', 'PAN'),
            ('passport', 'Passport'),
            ('driving_license', 'Driving License'),
            ('voter_id', 'Voter ID'),
        ],
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
        })
    )
    document_number = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
        })
    )
    document_files = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'accept': 'image/*,.pdf'
        }),
        required=True
    )


class PermissionAssignForm(forms.Form):
    """Permission assignment form"""
    
    user_id = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
        })
    )
    permission_id = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth.models import Permission
        self.fields['permission_id'].queryset = Permission.objects.all()


class RoleChangeForm(forms.Form):
    """Role change form"""
    
    user_id = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
        })
    )
    role_code = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
        })
    )
