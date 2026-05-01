"""
Django forms for portal app
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from portal.models import User, Profile, KYC, ParkPeServiceConfig, ParkPePaymentGatewayConfig
from portal.utils.validators import validate_phone_number
from django.core.exceptions import ValidationError


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


class SignUpForm(forms.Form):
    """Sign up form for self-onboarding (Customer/Retailer) - Creates User and Profile"""
    
    first_name = forms.CharField(
        label='First Name',
        required=True,
        error_messages={
            'required': 'Please enter your first name.'
        },
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter your first name'
        })
    )
    
    email = forms.EmailField(
        label='Email',
        required=True,
        error_messages={
            'required': 'Please enter your email address.',
            'invalid': 'Please enter a valid email address.'
        },
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter your email'
        })
    )
    
    phone = forms.CharField(
        label='Mobile Number',
        required=True,
        error_messages={
            'required': 'Please enter your mobile number.',
            'invalid': 'Please enter a valid mobile number.'
        },
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter your mobile number'
        }),
        validators=[validate_phone_number]
    )
    
    password1 = forms.CharField(
        label='Password',
        error_messages={
            'required': 'Please enter a password.',
            'min_length': 'Password must be at least 8 characters long.'
        },
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Create a password'
        }),
        min_length=8
    )
    password2 = forms.CharField(
        label='Confirm Password',
        error_messages={
            'required': 'Please confirm your password.'
        },
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Confirm your password'
        })
    )
    role_code = forms.ChoiceField(
        choices=[('customer', 'Customer'), ('retailer', 'Retailer')],
        error_messages={
            'required': 'Please select an account type.'
        },
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
        })
    )
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and Profile.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            validate_phone_number(phone)
            if Profile.objects.filter(phone=phone).exists():
                raise forms.ValidationError("A user with this mobile number already exists.")
        return phone


class SignInForm(forms.Form):
    """Sign in form — email, Payswap username (auto-generated ID), or registered Indian mobile."""
    
    username = forms.CharField(
        label='Email, Payswap ID, or mobile',
        error_messages={
            'required': 'Please enter your email, Payswap ID, or mobile number.'
        },
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Email, Payswap ID, or mobile',
            'autofocus': True
        })
    )
    password = forms.CharField(
        error_messages={
            'required': 'Please enter your password.'
        },
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter your password'
        })
    )
    remember = forms.BooleanField(required=False)
    
    def clean_username(self):
        """Allow email, Payswap ID, or Indian mobile (mobile resolved in SignInView)."""
        username = self.cleaned_data.get('username', '').strip()
        
        if not username:
            return username
        
        import re
        cleaned = username.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        looks_like_indian_mobile = bool(
            re.match(r'^(\+91|91|0)?[6-9]\d{9}$', cleaned)
            or (re.match(r'^\d{10}$', cleaned) and cleaned[0] in '6789')
        )
        
        if '@' in username:
            if not re.match(r'^[^@]+@[^@]+\.[^@]+$', username):
                raise forms.ValidationError('Please enter a valid email address.')
        elif looks_like_indian_mobile:
            pass  # SignInView resolves profile by phone
        else:
            if cleaned.isdigit() and len(cleaned) >= 10:
                raise forms.ValidationError(
                    'Use a valid email, your Payswap ID, or a 10-digit Indian mobile starting with 6–9.'
                )
        
        return username


class MFASetupForm(forms.Form):
    """MFA setup form"""
    
    mfa_method = forms.ChoiceField(
        choices=[('otp', 'OTP (SMS)'), ('authenticator', 'Authenticator App')],
        error_messages={
            'required': 'Please select an MFA method.'
        },
        widget=forms.RadioSelect(attrs={
            'class': 'mr-3'
        })
    )
    phone = forms.CharField(
        required=False,
        error_messages={
            'required': 'Please enter your phone number for OTP verification.'
        },
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter your phone number'
        })
    )
    totp_code = forms.CharField(
        required=False,
        max_length=6,
        error_messages={
            'required': 'Please enter the verification code from your authenticator app.',
            'max_length': 'Verification code must be 6 digits.'
        },
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
        error_messages={
            'required': 'Please enter the verification code.',
            'max_length': 'Verification code must be 6 digits.'
        },
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20 text-center text-2xl tracking-widest',
            'placeholder': '000000',
            'autofocus': True
        })
    )


# PIN: 4-digit numeric only. Used for session re-unlock after expiry; OTP/2FA is primary auth.
PIN_DIGITS = 4
PIN_REGEX = r'^\d{4}$'


class SetPinForm(forms.Form):
    """Set 4-digit PIN (secondary unlock only; requires full OTP/2FA auth first)."""
    
    pin = forms.CharField(
        max_length=PIN_DIGITS,
        min_length=PIN_DIGITS,
        strip=True,
        error_messages={
            'required': 'Please enter a 4-digit PIN.',
            'min_length': 'PIN must be exactly 4 digits.',
            'max_length': 'PIN must be exactly 4 digits.',
        },
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20 text-center text-xl tracking-widest',
            'placeholder': '••••',
            'autocomplete': 'off',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
        })
    )
    pin_confirm = forms.CharField(
        max_length=PIN_DIGITS,
        min_length=PIN_DIGITS,
        strip=True,
        label='Confirm PIN',
        error_messages={
            'required': 'Please confirm your PIN.',
            'min_length': 'PIN must be exactly 4 digits.',
            'max_length': 'PIN must be exactly 4 digits.',
        },
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20 text-center text-xl tracking-widest',
            'placeholder': '••••',
            'autocomplete': 'off',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
        })
    )
    
    def clean_pin(self):
        data = self.cleaned_data.get('pin')
        if data is not None and (len(data) != PIN_DIGITS or not data.isdigit()):
            raise ValidationError('PIN must be exactly 4 numeric digits.')
        return data
    
    def clean_pin_confirm(self):
        data = self.cleaned_data.get('pin_confirm')
        if data is not None and (len(data) != PIN_DIGITS or not data.isdigit()):
            raise ValidationError('PIN must be exactly 4 numeric digits.')
        return data
    
    def clean(self):
        cleaned = super().clean()
        pin = cleaned.get('pin')
        pin_confirm = cleaned.get('pin_confirm')
        if pin is not None and pin_confirm is not None and pin != pin_confirm:
            raise ValidationError({'pin_confirm': 'PIN and confirmation do not match.'})
        return cleaned


class UnlockPinForm(forms.Form):
    """Enter 4-digit PIN to re-unlock after session expiry (no OTP/2FA)."""
    
    pin = forms.CharField(
        max_length=PIN_DIGITS,
        min_length=PIN_DIGITS,
        strip=True,
        error_messages={
            'required': 'Please enter your PIN.',
            'min_length': 'PIN must be exactly 4 digits.',
            'max_length': 'PIN must be exactly 4 digits.',
        },
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20 text-center text-xl tracking-widest',
            'placeholder': '••••',
            'autocomplete': 'off',
            'inputmode': 'numeric',
            'pattern': '[0-9]*',
            'autofocus': True,
        })
    )
    
    def clean_pin(self):
        data = self.cleaned_data.get('pin')
        if data is not None and (len(data) != PIN_DIGITS or not data.isdigit()):
            raise ValidationError('PIN must be exactly 4 numeric digits.')
        return data


class ProfileCreateForm(forms.ModelForm):
    """Profile creation/update form"""
    BUSINESS_PROFILE_TYPES = {'business', 'corporate'}
    
    class Meta:
        model = Profile
        fields = ['first_name', 'last_name', 'middle_name', 'email', 'phone', 'date_of_birth', 
                  'gender', 'address_line_1', 'address_line_2', 'city', 'state', 'pincode', 
                  'type', 'business_name', 'business_registration_number', 'business_type',
                  'pan_number', 'aadhaar_number', 'gst_number', 'tax_id']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'middle_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
                'type': 'date'
            }),
            'gender': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'address_line_1': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
                'rows': 2
            }),
            'address_line_2': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
                'rows': 2
            }),
            'city': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'state': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'pincode': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'business_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'business_registration_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'business_type': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'pan_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'aadhaar_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'gst_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'tax_id': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
        }
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            validate_phone_number(phone)
        return phone

    def clean(self):
        cleaned_data = super().clean()
        profile_type = cleaned_data.get('type') or 'individual'
        if profile_type not in self.BUSINESS_PROFILE_TYPES:
            cleaned_data['business_name'] = None
            cleaned_data['business_registration_number'] = None
            cleaned_data['business_type'] = None
            cleaned_data['gst_number'] = None
            cleaned_data['tax_id'] = None
            return cleaned_data
        if not cleaned_data.get('business_name'):
            self.add_error('business_name', 'Business name is required for business/corporate profiles.')
        return cleaned_data


class UserCreateForm(forms.Form):
    """User creation form (for Admin) - Creates User and Profile"""
    
    first_name = forms.CharField(
        label='First Name',
        required=True,
        error_messages={
            'required': 'Please enter the user\'s first name.'
        },
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter first name'
        })
    )
    
    email = forms.EmailField(
        label='Email',
        required=True,
        error_messages={
            'required': 'Please enter the user\'s email address.',
            'invalid': 'Please enter a valid email address.'
        },
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter email address'
        })
    )
    
    phone = forms.CharField(
        label='Mobile Number',
        required=True,
        error_messages={
            'required': 'Please enter the user\'s mobile number.',
            'invalid': 'Please enter a valid mobile number.'
        },
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
    
    role_code = forms.ChoiceField(
        label='Role',
        choices=User.ROLE_CHOICES,
        required=True,
        error_messages={
            'required': 'Please select a role for the user.'
        },
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
        })
    )
    
    password1 = forms.CharField(
        label='Password',
        error_messages={
            'required': 'Please enter a password for the user.',
            'min_length': 'Password must be at least 8 characters long.'
        },
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
        }),
        min_length=8
    )
    password2 = forms.CharField(
        label='Confirm Password',
        error_messages={
            'required': 'Please confirm the password.'
        },
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
        })
    )
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match. Please try again.")
        return password2
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and Profile.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            validate_phone_number(phone)
            if Profile.objects.filter(phone=phone).exists():
                raise forms.ValidationError("A user with this mobile number already exists.")
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
        error_messages={
            'required': 'Please select a document type.'
        },
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
        })
    )
    document_number = forms.CharField(
        error_messages={
            'required': 'Please enter your document number.'
        },
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
        })
    )
    document_files = forms.FileField(
        error_messages={
            'required': 'Please upload your document file.'
        },
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


class ForgotPasswordForm(forms.Form):
    """Forgot password form - request password reset"""
    
    email = forms.EmailField(
        label='Email Address',
        required=True,
        error_messages={
            'required': 'Please enter your email address.',
            'invalid': 'Please enter a valid email address.'
        },
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter your email address',
            'autofocus': True
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check if user exists with this email in Profile
            try:
                profile = Profile.objects.get(email=email)
                if not profile.user.is_active:
                    raise forms.ValidationError("This account is inactive. Please contact support.")
            except Profile.DoesNotExist:
                # Don't reveal if email exists for security
                pass
        return email


class PasswordResetForm(forms.Form):
    """Password reset form with token"""
    
    password1 = forms.CharField(
        label='New Password',
        required=True,
        error_messages={
            'required': 'Please enter a new password.',
            'min_length': 'Password must be at least 8 characters long.'
        },
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter new password',
            'autofocus': True
        }),
        min_length=8
    )
    
    password2 = forms.CharField(
        label='Confirm New Password',
        required=True,
        error_messages={
            'required': 'Please confirm your new password.'
        },
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Confirm new password'
        })
    )
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match. Please try again.")
        return password2


class PasswordChangeForm(forms.Form):
    """Password change form for logged-in users"""
    
    old_password = forms.CharField(
        label='Current Password',
        required=True,
        error_messages={
            'required': 'Please enter your current password.'
        },
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter current password',
            'autofocus': True
        })
    )
    
    new_password1 = forms.CharField(
        label='New Password',
        required=True,
        error_messages={
            'required': 'Please enter a new password.',
            'min_length': 'Password must be at least 8 characters long.'
        },
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter new password'
        }),
        min_length=8
    )
    
    new_password2 = forms.CharField(
        label='Confirm New Password',
        required=True,
        error_messages={
            'required': 'Please confirm your new password.'
        },
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Confirm new password'
        })
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if old_password and not self.user.check_password(old_password):
            raise forms.ValidationError("Your current password is incorrect.")
        return old_password
    
    def clean_new_password2(self):
        new_password1 = self.cleaned_data.get('new_password1')
        new_password2 = self.cleaned_data.get('new_password2')
        if new_password1 and new_password2 and new_password1 != new_password2:
            raise forms.ValidationError("New passwords don't match. Please try again.")
        return new_password2


class ProfileUpdateForm(forms.ModelForm):
    """Profile update form"""
    BUSINESS_PROFILE_TYPES = {'business', 'corporate'}
    
    class Meta:
        model = Profile
        fields = [
            'first_name', 'middle_name', 'last_name', 'date_of_birth', 'gender', 'marital_status',
            'profile_photo', 'nationality', 'country_of_residence', 'state', 'city', 'pincode',
            'address_line_1', 'address_line_2', 'alternate_phone',
            'bank_name', 'account_holder_name', 'account_number', 'ifsc_code', 'branch_name', 'account_type',
            'pan_number', 'aadhaar_number', 'gst_number', 'tax_id',
            'type', 'business_name', 'business_registration_number', 'business_type',
            'language_preference', 'timezone', 'currency_preference',
            'recovery_email'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'middle_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
                'type': 'date'
            }),
            'gender': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'marital_status': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'profile_photo': forms.FileInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
                'accept': 'image/*'
            }),
            'nationality': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'country_of_residence': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'state': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'city': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'pincode': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'address_line_1': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
                'rows': 2
            }),
            'address_line_2': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
                'rows': 2
            }),
            'alternate_phone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'bank_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'account_holder_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'account_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'ifsc_code': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'branch_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'account_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'pan_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'aadhaar_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'gst_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'tax_id': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'business_name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'business_registration_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'business_type': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'language_preference': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'timezone': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'currency_preference': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'recovery_email': forms.EmailInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        profile_type = cleaned_data.get('type') or 'individual'
        if profile_type not in self.BUSINESS_PROFILE_TYPES:
            cleaned_data['business_name'] = None
            cleaned_data['business_registration_number'] = None
            cleaned_data['business_type'] = None
            cleaned_data['gst_number'] = None
            cleaned_data['tax_id'] = None
            return cleaned_data
        if not cleaned_data.get('business_name'):
            self.add_error('business_name', 'Business name is required for business/corporate profiles.')
        return cleaned_data


class ProfilePersonalForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'gender', 'marital_status',
            'nationality', 'profile_photo',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'input-enterprise'}),
            'first_name': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'middle_name': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'last_name': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'gender': forms.Select(attrs={'class': 'input-enterprise'}),
            'marital_status': forms.Select(attrs={'class': 'input-enterprise'}),
            'nationality': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'profile_photo': forms.FileInput(attrs={'class': 'input-enterprise', 'accept': 'image/*'}),
        }


class ProfileAddressForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'address_line_1', 'address_line_2', 'city', 'state', 'pincode',
            'country_of_residence', 'alternate_phone',
        ]
        widgets = {
            'address_line_1': forms.Textarea(attrs={'class': 'input-enterprise', 'rows': 2}),
            'address_line_2': forms.Textarea(attrs={'class': 'input-enterprise', 'rows': 2}),
            'city': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'state': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'pincode': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'country_of_residence': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'alternate_phone': forms.TextInput(attrs={'class': 'input-enterprise'}),
        }

    def clean_alternate_phone(self):
        phone = self.cleaned_data.get('alternate_phone')
        if phone:
            validate_phone_number(phone)
        return phone


class ProfileBankingForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'bank_name', 'account_holder_name', 'account_number',
            'ifsc_code', 'branch_name', 'account_type',
        ]
        widgets = {
            'bank_name': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'account_holder_name': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'account_number': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'ifsc_code': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'branch_name': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'account_type': forms.Select(attrs={'class': 'input-enterprise'}),
        }


class ProfileBusinessForm(forms.ModelForm):
    BUSINESS_PROFILE_TYPES = {'business', 'corporate'}

    class Meta:
        model = Profile
        fields = [
            'type', 'business_name', 'business_registration_number',
            'business_type', 'gst_number', 'tax_id',
        ]
        widgets = {
            'type': forms.Select(attrs={'class': 'input-enterprise'}),
            'business_name': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'business_registration_number': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'business_type': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'gst_number': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'tax_id': forms.TextInput(attrs={'class': 'input-enterprise'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        profile_type = cleaned_data.get('type') or 'individual'
        if profile_type not in self.BUSINESS_PROFILE_TYPES:
            cleaned_data['business_name'] = None
            cleaned_data['business_registration_number'] = None
            cleaned_data['business_type'] = None
            cleaned_data['gst_number'] = None
            cleaned_data['tax_id'] = None
        elif not cleaned_data.get('business_name'):
            self.add_error('business_name', 'Business name is required for business/corporate profiles.')
        return cleaned_data


class ProfileIdentityForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['pan_number', 'aadhaar_number']
        widgets = {
            'pan_number': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'aadhaar_number': forms.TextInput(attrs={'class': 'input-enterprise'}),
        }


class ProfileSecurityPrefsForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'language_preference', 'timezone', 'currency_preference',
            'recovery_email', 'notification_preferences',
        ]
        widgets = {
            'language_preference': forms.Select(attrs={'class': 'input-enterprise'}),
            'timezone': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'currency_preference': forms.TextInput(attrs={'class': 'input-enterprise'}),
            'recovery_email': forms.EmailInput(attrs={'class': 'input-enterprise'}),
            'notification_preferences': forms.HiddenInput(),
        }


class ProfileCompletionForm(forms.Form):
    """Profile completion form for social signup users - Required fields"""
    
    phone = forms.CharField(
        label='Mobile Number',
        required=True,
        error_messages={
            'required': 'Mobile number is required to complete your profile.'
        },
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter your mobile number'
        }),
        validators=[validate_phone_number]
    )
    
    address_line_1 = forms.CharField(
        label='Address Line 1',
        required=True,
        error_messages={
            'required': 'Address is required to complete your profile.'
        },
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter your address',
            'rows': 3
        })
    )
    
    address_line_2 = forms.CharField(
        label='Address Line 2',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Apartment, suite, etc. (optional)',
            'rows': 2
        })
    )
    
    city = forms.CharField(
        label='City',
        required=True,
        error_messages={
            'required': 'City is required.'
        },
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter your city'
        })
    )
    
    state = forms.CharField(
        label='State',
        required=True,
        error_messages={
            'required': 'State is required.'
        },
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter your state'
        })
    )
    
    pincode = forms.CharField(
        label='Pincode',
        required=True,
        error_messages={
            'required': 'Pincode is required.'
        },
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter your pincode'
        }),
        max_length=10
    )
    
    date_of_birth = forms.DateField(
        label='Date of Birth',
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'type': 'date'
        }),
        help_text='Optional but recommended for account security'
    )
    
    def clean_phone(self):
        """Validate phone number uniqueness"""
        phone = self.cleaned_data.get('phone')
        if phone:
            # Check if phone already exists (excluding current user's profile)
            from portal.models import Profile
            if hasattr(self, 'user') and self.user and hasattr(self.user, 'profile'):
                existing = Profile.objects.filter(phone=phone).exclude(user=self.user).exists()
            else:
                existing = Profile.objects.filter(phone=phone).exists()
            
            if existing:
                raise forms.ValidationError('This mobile number is already registered.')
        
        return phone


class OTPVerifyForm(forms.Form):
    """OTP verification form for signup"""
    
    otp_code = forms.CharField(
        label='Verification Code',
        required=True,
        max_length=6,
        min_length=6,
        error_messages={
            'required': 'Please enter the verification code.',
            'min_length': 'Verification code must be 6 digits.',
            'max_length': 'Verification code must be 6 digits.'
        },
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20 text-center text-2xl tracking-widest',
            'placeholder': '000000',
            'maxlength': '6',
            'pattern': '[0-9]{6}',
            'inputmode': 'numeric'
        })
    )
    
    def clean_otp_code(self):
        """Validate OTP code format"""
        otp_code = self.cleaned_data.get('otp_code')
        if otp_code and not otp_code.isdigit():
            raise forms.ValidationError('Verification code must contain only digits.')
        return otp_code


# ============================================================================
# BRAND ONBOARDING FORMS
# ============================================================================

class BrandOnboardingStep1Form(forms.Form):
    """Step 1: Basic Information"""
    
    brand_name = forms.CharField(
        label='Brand Name',
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter brand name'
        })
    )
    contact_person = forms.CharField(
        label='Contact Person',
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter contact person name'
        })
    )
    contact_email = forms.EmailField(
        label='Contact Email',
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter email address'
        })
    )
    contact_phone = forms.CharField(
        label='Contact Phone',
        required=True,
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter phone number'
        })
    )
    address = forms.CharField(
        label='Business Address',
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea-enterprise',
            'rows': 3,
            'placeholder': 'Enter business address'
        })
    )


class BrandOnboardingStep2Form(forms.Form):
    """Step 2: Business Details"""
    
    business_type = forms.ChoiceField(
        label='Business Type',
        required=True,
        choices=[
            ('', 'Select business type'),
            ('LLP', 'Limited Liability Partnership'),
            ('PRIVATE_LTD', 'Private Limited'),
            ('PUBLIC_LTD', 'Public Limited'),
            ('PARTNERSHIP', 'Partnership'),
            ('SOLE_PROPRIETORSHIP', 'Sole Proprietorship'),
            ('HUF', 'Hindu Undivided Family'),
            ('OTHER', 'Other'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select-enterprise'
        })
    )
    business_reg_no = forms.CharField(
        label='Business Registration Number',
        required=True,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter registration number'
        })
    )
    pan_number = forms.CharField(
        label='PAN Number',
        required=False,
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter PAN (10 characters)',
            'maxlength': '10'
        })
    )
    gst_number = forms.CharField(
        label='GST Number',
        required=False,
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter GSTIN (15 characters)',
            'maxlength': '15'
        })
    )
    
    def clean_pan_number(self):
        pan = self.cleaned_data.get('pan_number', '').strip().upper()
        if pan and len(pan) != 10:
            raise forms.ValidationError('PAN must be exactly 10 characters')
        return pan
    
    def clean_gst_number(self):
        gst = self.cleaned_data.get('gst_number', '').strip().upper()
        if gst and len(gst) != 15:
            raise forms.ValidationError('GST number must be exactly 15 characters')
        return gst


class BrandOnboardingStep3Form(forms.Form):
    """Step 3: Banking Information"""
    
    bank_account_number = forms.CharField(
        label='Bank Account Number',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter account number',
            'type': 'text'
        })
    )
    bank_ifsc_code = forms.CharField(
        label='IFSC Code',
        required=True,
        max_length=11,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter IFSC code (11 characters)',
            'maxlength': '11'
        })
    )
    bank_name = forms.CharField(
        label='Bank Name',
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter bank name'
        })
    )
    account_holder_name = forms.CharField(
        label='Account Holder Name',
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter account holder name'
        })
    )
    
    def clean_bank_ifsc_code(self):
        ifsc = self.cleaned_data.get('bank_ifsc_code', '').strip().upper()
        if len(ifsc) != 11:
            raise forms.ValidationError('IFSC code must be exactly 11 characters')
        return ifsc
    
    def clean_bank_account_number(self):
        account = self.cleaned_data.get('bank_account_number', '').strip()
        if account and (len(account) < 9 or not account.isdigit()):
            raise forms.ValidationError('Invalid account number')
        return account


class BrandOnboardingStep4Form(forms.Form):
    """Step 4: Document Upload"""
    
    business_registration_doc = forms.FileField(
        label='Business Registration Document',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-input-enterprise',
            'accept': '.pdf,.jpg,.jpeg,.png'
        })
    )
    pan_document = forms.FileField(
        label='PAN Document',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-input-enterprise',
            'accept': '.pdf,.jpg,.jpeg,.png'
        })
    )
    gst_certificate = forms.FileField(
        label='GST Certificate',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-input-enterprise',
            'accept': '.pdf,.jpg,.jpeg,.png'
        })
    )
    bank_statement = forms.FileField(
        label='Bank Statement',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-input-enterprise',
            'accept': '.pdf,.jpg,.jpeg,.png'
        })
    )
    agreement_document = forms.FileField(
        label='Signed Agreement',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-input-enterprise',
            'accept': '.pdf,.jpg,.jpeg,.png'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        # Check if required documents are provided (either new upload or existing URL)
        # This validation is handled in the view since we need to check existing URLs
        return cleaned_data


class BrandOnboardingStep5Form(forms.Form):
    """Step 5: Terms & Agreement"""
    
    terms_accepted = forms.BooleanField(
        label='I accept the terms and conditions',
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox-enterprise'
        })
    )
    agreement_signed = forms.BooleanField(
        label='I confirm that the agreement has been signed',
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox-enterprise'
        })
    )


class BrandOnboardingReviewForm(forms.Form):
    """Step 6: Review & Submit"""
    # Review form doesn't need fields - it's just a confirmation
    confirm_submit = forms.BooleanField(
        label='I confirm all information is correct and ready to submit',
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox-enterprise'
        })
    )


class BrandOnboardingAdminApprovalForm(forms.Form):
    """Admin approval/rejection form"""
    
    action = forms.ChoiceField(
        label='Action',
        required=True,
        choices=[
            ('approve', 'Approve'),
            ('reject', 'Reject'),
        ],
        widget=forms.RadioSelect(attrs={
            'class': 'form-radio-enterprise'
        })
    )
    onboarding_notes = forms.CharField(
        label='Notes',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea-enterprise',
            'rows': 4,
            'placeholder': 'Add notes about this review (optional)'
        })
    )
    rejection_reason = forms.CharField(
        label='Rejection Reason',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea-enterprise',
            'rows': 4,
            'placeholder': 'Explain why the onboarding is being rejected'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        rejection_reason = cleaned_data.get('rejection_reason')
        
        if action == 'reject' and not rejection_reason:
            raise forms.ValidationError({
                'rejection_reason': 'Rejection reason is required when rejecting onboarding'
            })
        
        return cleaned_data


class ResellerOnboardingStep1Form(forms.Form):
    """Reseller Partner Onboarding - Step 1: Company Information"""
    
    company_name = forms.CharField(
        label='Company Name',
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
            'placeholder': 'Enter company name'
        })
    )
    
    business_type = forms.ChoiceField(
        label='Business Type',
        required=True,
        choices=[
            ('', 'Select...'),
            ('LLP', 'Limited Liability Partnership'),
            ('PRIVATE_LTD', 'Private Limited'),
            ('PUBLIC_LTD', 'Public Limited'),
            ('PARTNERSHIP', 'Partnership'),
            ('SOLE_PROPRIETORSHIP', 'Sole Proprietorship'),
            ('HUF', 'Hindu Undivided Family'),
            ('OTHER', 'Other'),
        ],
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'
        })
    )
    
    gst_number = forms.CharField(
        label='GST Number',
        required=False,
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
            'placeholder': 'Optional'
        })
    )
    
    address = forms.CharField(
        label='Business Address',
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
            'rows': 4,
            'placeholder': 'Enter complete business address'
        })
    )


class ResellerOnboardingStep2Form(forms.Form):
    """Reseller Partner Onboarding - Step 2: Contact Details"""
    
    contact_person = forms.CharField(
        label='Contact Person Name',
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
            'placeholder': 'Enter contact person name'
        })
    )
    
    phone = forms.CharField(
        label='Phone Number',
        required=True,
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
            'placeholder': '+91XXXXXXXXXX'
        })
    )


def _get_vendor_queryset(codes):
    """Return active ApiVendor queryset for given codes (used by onboarding form)."""
    from portal.models import ApiVendor
    return ApiVendor.objects.filter(is_active=True, code__in=codes).order_by('name')


class AdminResellerPartnerOnboardForm(forms.Form):
    """Admin form for onboarding reseller partners (includes vendor assignment)."""
    
    company_name = forms.CharField(
        label='Company Name',
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
            'placeholder': 'Enter company name'
        })
    )
    
    contact_person = forms.CharField(
        label='Contact Person',
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
            'placeholder': 'Contact person name'
        })
    )
    
    email = forms.EmailField(
        label='Email',
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
            'placeholder': 'business@example.com'
        })
    )
    
    phone = forms.CharField(
        label='Phone',
        required=True,
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
            'placeholder': '+919876543210'
        })
    )
    
    business_type = forms.ChoiceField(
        label='Business Type',
        required=True,
        choices=[
            ('LLP', 'Limited Liability Partnership'),
            ('PRIVATE_LTD', 'Private Limited'),
            ('PUBLIC_LTD', 'Public Limited'),
            ('PARTNERSHIP', 'Partnership'),
            ('SOLE_PROPRIETORSHIP', 'Sole Proprietorship'),
            ('HUF', 'Hindu Undivided Family'),
            ('OTHER', 'Other'),
        ],
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'
        })
    )
    
    gst_number = forms.CharField(
        label='GST Number',
        required=False,
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
            'placeholder': 'Optional'
        })
    )
    
    address = forms.CharField(
        label='Business Address',
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md',
            'rows': 4,
            'placeholder': 'Enter complete business address'
        })
    )
    
    auto_approve = forms.BooleanField(
        label='Auto-approve onboarding',
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'mr-2'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.forms import ModelMultipleChoiceField, ModelChoiceField
        from portal.models import ApiVendor
        qs = ApiVendor.objects.filter(is_active=True).order_by('name')
        # BBPS: Euronet, Mobikwik
        bbps_qs = qs.filter(code__in=['euronet', 'mobikwik'])
        self.fields['bbps_vendors'] = ModelMultipleChoiceField(
            queryset=bbps_qs, required=False, label='BBPS vendors',
            widget=forms.CheckboxSelectMultiple(attrs={'class': 'mr-2'})
        )
        self.fields['bbps_primary_vendor'] = ModelChoiceField(
            queryset=bbps_qs, required=False, label='BBPS primary vendor'
        )
        # KYC: Cashfree, Instantpay
        kyc_qs = qs.filter(code__in=['cashfree', 'instantpay'])
        self.fields['kyc_vendors'] = ModelMultipleChoiceField(
            queryset=kyc_qs, required=False, label='KYC vendors',
            widget=forms.CheckboxSelectMultiple(attrs={'class': 'mr-2'})
        )
        self.fields['kyc_primary_vendor'] = ModelChoiceField(queryset=kyc_qs, required=False, label='KYC primary')
        # SMS: Kaleyra
        sms_qs = qs.filter(code='kaleyra')
        self.fields['sms_vendors'] = ModelMultipleChoiceField(
            queryset=sms_qs, required=False, label='SMS vendors',
            widget=forms.CheckboxSelectMultiple(attrs={'class': 'mr-2'})
        )
        self.fields['sms_primary_vendor'] = ModelChoiceField(queryset=sms_qs, required=False, label='SMS primary')
        # Payment: Cashfree PG
        payment_qs = qs.filter(code='cashfree_pg')
        self.fields['payment_vendors'] = ModelMultipleChoiceField(
            queryset=payment_qs, required=False, label='Payment vendors',
            widget=forms.CheckboxSelectMultiple(attrs={'class': 'mr-2'})
        )
        self.fields['payment_primary_vendor'] = ModelChoiceField(
            queryset=payment_qs, required=False, label='Payment primary'
        )


class BrandAdminOnboardingForm(forms.Form):
    """Combined form for admin to create and onboard brand in one flow"""
    
    # Step 1: Basic Information
    brand_name = forms.CharField(
        label='Brand Name',
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter brand name'
        })
    )
    contact_person = forms.CharField(
        label='Contact Person',
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter contact person name'
        })
    )
    contact_email = forms.EmailField(
        label='Contact Email',
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter email address'
        })
    )
    contact_phone = forms.CharField(
        label='Contact Phone',
        required=True,
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter phone number'
        })
    )
    address = forms.CharField(
        label='Business Address',
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea-enterprise',
            'rows': 3,
            'placeholder': 'Enter business address'
        })
    )
    
    # Step 2: Business Details
    business_type = forms.ChoiceField(
        label='Business Type',
        required=True,
        choices=[
            ('', 'Select business type'),
            ('LLP', 'Limited Liability Partnership'),
            ('PRIVATE_LTD', 'Private Limited'),
            ('PUBLIC_LTD', 'Public Limited'),
            ('PARTNERSHIP', 'Partnership'),
            ('SOLE_PROPRIETORSHIP', 'Sole Proprietorship'),
            ('HUF', 'Hindu Undivided Family'),
            ('OTHER', 'Other'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select-enterprise'
        })
    )
    business_reg_no = forms.CharField(
        label='Business Registration Number',
        required=True,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter registration number'
        })
    )
    pan_number = forms.CharField(
        label='PAN Number',
        required=False,
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter PAN (10 characters)',
            'maxlength': '10'
        })
    )
    gst_number = forms.CharField(
        label='GST Number',
        required=False,
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter GSTIN (15 characters)',
            'maxlength': '15'
        })
    )
    
    # Step 3: Banking Information
    bank_account_number = forms.CharField(
        label='Bank Account Number',
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter account number',
            'type': 'text'
        })
    )
    bank_ifsc_code = forms.CharField(
        label='IFSC Code',
        required=True,
        max_length=11,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter IFSC code (11 characters)',
            'maxlength': '11'
        })
    )
    bank_name = forms.CharField(
        label='Bank Name',
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter bank name'
        })
    )
    account_holder_name = forms.CharField(
        label='Account Holder Name',
        required=True,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input-enterprise',
            'placeholder': 'Enter account holder name'
        })
    )
    
    # Step 5: Agreement
    terms_accepted = forms.BooleanField(
        label='Terms and conditions accepted',
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox-enterprise'
        })
    )
    agreement_signed = forms.BooleanField(
        label='Agreement signed',
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox-enterprise'
        })
    )
    
    # Admin options
    auto_approve = forms.BooleanField(
        label='Auto-approve after creation',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox-enterprise'
        }),
        help_text='If checked, brand will be automatically approved and activated'
    )
    
    def clean_pan_number(self):
        pan = self.cleaned_data.get('pan_number', '').strip().upper()
        if pan and len(pan) != 10:
            raise forms.ValidationError('PAN must be exactly 10 characters')
        return pan
    
    def clean_gst_number(self):
        gst = self.cleaned_data.get('gst_number', '').strip().upper()
        if gst and len(gst) != 15:
            raise forms.ValidationError('GST number must be exactly 15 characters')
        return gst
    
    def clean_bank_ifsc_code(self):
        ifsc = self.cleaned_data.get('bank_ifsc_code', '').strip().upper()
        if len(ifsc) != 11:
            raise forms.ValidationError('IFSC code must be exactly 11 characters')
        return ifsc
    
    def clean_bank_account_number(self):
        account = self.cleaned_data.get('bank_account_number', '').strip()
        if account and (len(account) < 9 or not account.isdigit()):
            raise forms.ValidationError('Invalid account number')
        return account


# ParkPe App Management (Backend UI – no Django admin)
class ParkPeServiceConfigForm(forms.ModelForm):
    class Meta:
        model = ParkPeServiceConfig
        fields = ('service_code', 'voucher_allowed', 'pg_allowed', 'is_active')
        widgets = {
            'service_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. BBPS'}),
            'voucher_allowed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'pg_allowed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ParkPePaymentGatewayConfigForm(forms.ModelForm):
    class Meta:
        model = ParkPePaymentGatewayConfig
        fields = ('gateway', 'service_code', 'enabled', 'is_default_for_voucher_purchase', 'merchant_id', 'credential_key')
        labels = {
            'merchant_id': 'Merchant ID',
            'credential_key': 'Credential key (Key ID / App ID)',
        }
        widgets = {
            'gateway': forms.Select(attrs={'class': 'form-select'}),
            'service_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Leave empty for voucher purchase'}),
            'enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_default_for_voucher_purchase': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'merchant_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. MCH_RAZORPAY_001 — is service ke liye kaun sa merchant'}),
            'credential_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Razorpay: Key ID. Cashfree: App ID (x-client-id). Optional if .env use kar rahe ho'}),
        }

