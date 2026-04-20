"""
Portal profile and settings views.
"""
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import DetailView, CreateView, UpdateView, TemplateView

from portal.models import Profile
from portal.forms import ProfileCreateForm, ProfileUpdateForm
from portal.services.settings_service import get_settings_payload, update_user_settings
from portal.models import UserSettingsAuditLog


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
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Profile created successfully!')
        return super().form_valid(form)


class ProfileView(DetailView):
    """Profile view for logged-in users"""
    model = Profile
    template_name = 'portal/profile/view.html'
    context_object_name = 'profile'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_object(self):
        if not hasattr(self.request.user, 'profile'):
            messages.error(self.request, 'Profile not found. Please create your profile.')
            return redirect('/profile/create/')
        return self.request.user.profile


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


class SettingsView(TemplateView):
    """Settings view for logged-in users"""
    template_name = 'portal/settings.html'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        profile = getattr(self.request.user, "profile", None)
        ctx["profile"] = profile
        ctx["settings_payload"] = get_settings_payload(self.request.user)
        return ctx

    def post(self, request, *args, **kwargs):
        profile = getattr(request.user, "profile", None)
        if not profile:
            messages.error(request, "Profile not found.")
            return redirect("/profile/create/")

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
        messages.success(request, "Settings updated successfully.")
        return redirect("/settings/")
