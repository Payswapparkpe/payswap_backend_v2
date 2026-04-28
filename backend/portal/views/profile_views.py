"""
Portal profile and settings views.
"""
from django.shortcuts import redirect, render
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views import View
from django.views.generic import CreateView, UpdateView

from portal.models import KYC, Profile, Wallet
from portal.forms import (
    KYCSubmitForm,
    ProfileAddressForm,
    ProfileBankingForm,
    ProfileBusinessForm,
    ProfileCreateForm,
    ProfileIdentityForm,
    ProfilePersonalForm,
    ProfileSecurityPrefsForm,
    ProfileUpdateForm,
)
from portal.services.settings_service import get_settings_payload, update_user_settings
from portal.models import UserSettingsAuditLog

VALID_TABS = {'overview', 'personal', 'banking', 'business', 'kyc', 'security'}


def _compute_profile_completion(profile):
    """Return completion percentage and missing profile items."""
    is_business_profile = getattr(profile, "type", "individual") in {"business", "corporate"}
    checks = [
        ("first_name", "Add first name", "/profile/?tab=personal"),
        ("phone", "Add phone number", "/profile/?tab=personal"),
        ("address_line_1", "Add address", "/profile/?tab=personal"),
        ("city", "Add city", "/profile/?tab=personal"),
        ("state", "Add state", "/profile/?tab=personal"),
        ("pincode", "Add pincode", "/profile/?tab=personal"),
        ("pan_number", "Add PAN number", "/profile/?tab=business"),
        ("date_of_birth", "Add date of birth", "/profile/?tab=personal"),
        ("recovery_email", "Add recovery email", "/profile/?tab=security"),
        ("phone_verified", "Verify phone number", "/profile/?tab=personal"),
    ]
    if is_business_profile:
        checks.extend([
            ("business_name", "Add business name", "/profile/?tab=business"),
            ("business_registration_number", "Add business registration number", "/profile/?tab=business"),
            ("gst_number", "Add GSTIN", "/profile/?tab=business"),
        ])
    completed = 0
    missing = []
    for field_name, label, link in checks:
        value = getattr(profile, field_name, None)
        is_done = bool(value)
        if is_done:
            completed += 1
        else:
            missing.append({"label": label, "link": link})
    percentage = int(round((completed / len(checks)) * 100))
    return percentage, missing


class ProfileCreateView(CreateView):
    """Profile creation view"""
    model = Profile
    form_class = ProfileCreateForm
    template_name = 'portal/profile/create.html'
    success_url = '/dashboard/'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Profile created successfully!')
        return super().form_valid(form)


class ProfileView(View):
    """Unified profile hub view (tabs under one URL)."""
    template_name = 'portal/profile/index.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def _get_profile_or_redirect(self):
        if not hasattr(self.request.user, 'profile'):
            messages.error(self.request, 'Profile not found. Please create your profile.')
            return None, redirect('/profile/create/')
        return self.request.user.profile, None

    def _get_tab(self):
        tab = (self.request.GET.get('tab') or 'overview').strip().lower()
        return tab if tab in VALID_TABS else 'overview'

    def _build_context(self, profile, active_tab, forms_override=None):
        forms_override = forms_override or {}
        user = self.request.user
        completion_pct, completion_missing_items = _compute_profile_completion(profile)
        kyc_obj = getattr(user, 'kyc', None)
        ctx = {
            "user": user,
            "profile": profile,
            "active_tab": active_tab,
            "kyc": kyc_obj,
            "wallet": Wallet.objects.filter(user=user).first(),
            "completion_pct": completion_pct,
            "completion_missing_items": completion_missing_items,
            "is_business_profile": profile.type in {"business", "corporate"},
            "settings_payload": get_settings_payload(user),
            "personal_form": forms_override.get("personal_form") or ProfilePersonalForm(instance=profile),
            "address_form": forms_override.get("address_form") or ProfileAddressForm(instance=profile),
            "banking_form": forms_override.get("banking_form") or ProfileBankingForm(instance=profile),
            "business_form": forms_override.get("business_form") or ProfileBusinessForm(instance=profile),
            "identity_form": forms_override.get("identity_form") or ProfileIdentityForm(instance=profile),
            "security_form": forms_override.get("security_form") or ProfileSecurityPrefsForm(instance=profile),
            "kyc_form": forms_override.get("kyc_form") or KYCSubmitForm(),
        }
        return ctx

    def get(self, request, *args, **kwargs):
        profile, redirect_response = self._get_profile_or_redirect()
        if redirect_response:
            return redirect_response
        active_tab = self._get_tab()
        context = self._build_context(profile, active_tab=active_tab)
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        profile, redirect_response = self._get_profile_or_redirect()
        if redirect_response:
            return redirect_response
        section = (request.POST.get('section') or '').strip().lower()
        if section not in VALID_TABS:
            section = 'overview'
        if section in {'overview'}:
            return redirect('/profile/?tab=overview')

        if section == 'personal':
            personal_form = ProfilePersonalForm(request.POST, request.FILES, instance=profile)
            address_form = ProfileAddressForm(request.POST, instance=profile)
            if personal_form.is_valid() and address_form.is_valid():
                personal_form.save()
                address_form.save()
                messages.success(request, 'Personal details updated successfully.')
                return redirect('/profile/?tab=personal')
            context = self._build_context(
                profile,
                active_tab='personal',
                forms_override={"personal_form": personal_form, "address_form": address_form},
            )
            return render(request, self.template_name, context)

        if section == 'banking':
            banking_form = ProfileBankingForm(request.POST, instance=profile)
            if banking_form.is_valid():
                banking_form.save()
                messages.success(request, 'Banking details updated successfully.')
                return redirect('/profile/?tab=banking')
            context = self._build_context(profile, active_tab='banking', forms_override={"banking_form": banking_form})
            return render(request, self.template_name, context)

        if section == 'business':
            if profile.type in {'business', 'corporate'} or (request.POST.get('type') in {'business', 'corporate'}):
                business_form = ProfileBusinessForm(request.POST, instance=profile)
                if business_form.is_valid():
                    business_form.save()
                    messages.success(request, 'Business details updated successfully.')
                    return redirect('/profile/?tab=business')
                context = self._build_context(profile, active_tab='business', forms_override={"business_form": business_form})
                return render(request, self.template_name, context)
            identity_form = ProfileIdentityForm(request.POST, instance=profile)
            if identity_form.is_valid():
                identity_form.save()
                messages.success(request, 'Identity details updated successfully.')
                return redirect('/profile/?tab=business')
            context = self._build_context(profile, active_tab='business', forms_override={"identity_form": identity_form})
            return render(request, self.template_name, context)

        if section == 'security':
            security_form = ProfileSecurityPrefsForm(request.POST, instance=profile)
            if security_form.is_valid():
                security_form.save()
                updates = {
                    "preferences": {
                        "language": request.POST.get("language_preference", profile.language_preference),
                        "timezone": request.POST.get("timezone", profile.timezone),
                        "currency": request.POST.get("currency_preference", profile.currency_preference),
                    },
                    "notificationPreferences": {
                        "push": request.POST.get("notif_push") == "on",
                        "email": request.POST.get("notif_email") == "on",
                        "sms": request.POST.get("notif_sms") == "on",
                        "in_app": request.POST.get("notif_in_app") == "on",
                        "quiet_hours_enabled": request.POST.get("quiet_hours_enabled") == "on",
                        "quiet_hours_start": request.POST.get("quiet_hours_start") or "22:00",
                        "quiet_hours_end": request.POST.get("quiet_hours_end") or "07:00",
                        "critical_alert_override": request.POST.get("critical_alert_override") == "on",
                    },
                    "privacy": {
                        "marketingConsent": request.POST.get("privacy_marketing") == "on",
                        "productTips": request.POST.get("privacy_product_tips") == "on",
                        "securityAlerts": request.POST.get("privacy_security_alerts") == "on",
                    },
                }
                update_user_settings(
                    user=request.user,
                    updates=updates,
                    actor_user=request.user,
                    source=UserSettingsAuditLog.SOURCE_HUB,
                    request=request,
                )
                messages.success(request, 'Security and preferences updated successfully.')
                return redirect('/profile/?tab=security')
            context = self._build_context(profile, active_tab='security', forms_override={"security_form": security_form})
            return render(request, self.template_name, context)

        if section == 'kyc':
            kyc_form = KYCSubmitForm(request.POST, request.FILES)
            if kyc_form.is_valid():
                kyc_obj, _ = KYC.objects.update_or_create(
                    user=request.user,
                    defaults={
                        "document_type": kyc_form.cleaned_data['document_type'],
                        "document_number": kyc_form.cleaned_data['document_number'],
                        "status": 'submitted',
                    },
                )
                files = request.FILES.getlist('document_files')
                if files:
                    from portal.services.storage_service import StorageService
                    storage = StorageService()
                    document_urls = []
                    document_keys = []
                    for file in files:
                        key = storage.build_kyc_document_key(request.user.id, kyc_form.cleaned_data['document_type'], file.name)
                        url = storage.upload_kyc_document(request.user.id, kyc_form.cleaned_data['document_type'], file)
                        document_urls.append(url)
                        document_keys.append(key)
                    kyc_obj.document_files = document_urls
                    kyc_obj.document_file_keys = document_keys
                    kyc_obj.save(update_fields=['document_files', 'document_file_keys'])
                if hasattr(request.user, 'kyc_status'):
                    request.user.kyc_status = 'submitted'
                    request.user.save(update_fields=['kyc_status'])
                messages.success(request, 'KYC details submitted successfully.')
                return redirect('/profile/?tab=kyc')
            context = self._build_context(profile, active_tab='kyc', forms_override={"kyc_form": kyc_form})
            return render(request, self.template_name, context)

        return redirect('/profile/?tab=overview')


class ProfileUpdateView(UpdateView):
    """Profile update view"""
    model = Profile
    form_class = ProfileUpdateForm
    template_name = 'portal/profile/update.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_object(self):
        if not hasattr(self.request.user, 'profile'):
            messages.error(self.request, 'Profile not found. Please create your profile.')
            return redirect('/profile/create/')
        return self.request.user.profile

    def form_valid(self, form):
        form.instance.last_updated_by = self.request.user
        messages.success(self.request, 'Profile updated successfully!')
        return super().form_valid(form)

    def get_success_url(self):
        return '/profile/'


class SettingsView(View):
    """Settings view for logged-in users"""
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return redirect('/profile/?tab=security')


class ProfileSaveView(ProfileView):
    """Dedicated endpoint for section-wise profile saves."""

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        return redirect('/profile/')
