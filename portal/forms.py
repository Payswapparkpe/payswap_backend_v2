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
    """Sign in form"""
    
    username = forms.CharField(
        error_messages={
            'required': 'Please enter your username or email address.'
        },
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20',
            'placeholder': 'Enter your username',
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


class ProfileCreateForm(forms.ModelForm):
    """Profile creation/update form"""
    
    class Meta:
        model = Profile
        fields = ['first_name', 'last_name', 'middle_name', 'email', 'phone', 'date_of_birth', 
                  'gender', 'address_line_1', 'address_line_2', 'city', 'state', 'pincode', 
                  'type', 'business_name', 'pan_number', 'aadhaar_number', 'gst_number']
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
            'pan_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'aadhaar_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
            'gst_number': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:border-[#0066CC] focus:ring-2 focus:ring-[#0066CC] focus:ring-opacity-20'
            }),
        }
    
    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            validate_phone_number(phone)
        return phone


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
