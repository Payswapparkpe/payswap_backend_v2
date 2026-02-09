"""
API URL Configuration with Versioning
- v1: Internal access (staff/authenticated users)
- v2: External parties (public/API keys)
"""
from django.urls import path, include

urlpatterns = [
    path("v1/", include("api.v1.urls")),  # Internal API
    path("v2/", include("api.v2.urls")),  # External API
    path("auth/", include("api.auth_parkpe.urls")),  # Parkpe Angular (login, profile, JWT)
    path("connect/", include("api.connect.urls")),  # ParkPe Connect (vehicle, QR, contact)
    path("bbps/", include("api.bbps_parkpe.urls")),  # Parkpe Angular (Mobikwik BBPS)
    path("dashboard/", include("api.parkpe_api.urls")),  # Parkpe dashboard summary
    path("payment/", include("api.parkpe_api.payment_urls")),  # Parkpe payment transactions
    path("voucher/", include("api.parkpe_api.voucher_urls")),   # Parkpe voucher balance (no wallet)
]
