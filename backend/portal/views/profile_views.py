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
