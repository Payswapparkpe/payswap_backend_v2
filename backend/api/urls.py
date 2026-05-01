"""
API URL Configuration with Versioning
- v1: Internal access (staff/authenticated users)
- v2: External parties (public/API keys)
- dashboard/: ParkPe summary, pincode
"""
from django.urls import path, include

urlpatterns = [
    path("v1/", include("api.v1.urls")),  # Internal API
    path("v2/", include("api.v2.urls")),  # External API
    path("hub/", include("rbac.urls")),   # Hub RBAC (departments, projects, roles, assignments)
    path("dashboard/", include("api.urls_dashboard")),  # ParkPe summary, pincode
    path("auth/", include("api.auth_parkpe.urls")),  # Parkpe Angular (login, profile, JWT)
    path("connect/", include("api.connect.urls")),  # ParkPe Connect (vehicle, QR, contact)
    path("bbps/", include("api.bbps_parkpe.urls")),  # Parkpe Angular (Mobikwik BBPS)
    path("payment/", include("api.parkpe_api.payment_urls")),  # Parkpe payment transactions
    path("fastag/", include("api.parkpe_api.fastag_urls")),  # Parkpe FASTag recharge
    path("voucher/", include("api.parkpe_api.voucher_urls")),   # Parkpe voucher balance (no wallet)
    path("challan/", include("api.parkpe_api.challan_urls")),  # Parkpe Challan (Instantpay lookup)
    path("parking/", include("api.parkpe_api.parking_urls")),  # Parkpe Smart Parking Platform
]
