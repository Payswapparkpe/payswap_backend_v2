from django.urls import path
from .views import (
    AuthLoginView,
    AuthOTPRequestView,
    AuthOTPVerifyView,
    AuthRegisterView,
    AuthProfileView,
    AuthLogoutView,
    AuthForgotPasswordView,
)

urlpatterns = [
    path("login", AuthLoginView.as_view(), name="auth-parkpe-login"),
    path("otp/request", AuthOTPRequestView.as_view(), name="auth-parkpe-otp-request"),
    path("otp/verify", AuthOTPVerifyView.as_view(), name="auth-parkpe-otp-verify"),
    path("register", AuthRegisterView.as_view(), name="auth-parkpe-register"),
    path("profile", AuthProfileView.as_view(), name="auth-parkpe-profile"),
    path("logout", AuthLogoutView.as_view(), name="auth-parkpe-logout"),
    path("forgot-password", AuthForgotPasswordView.as_view(), name="auth-parkpe-forgot-password"),
]
