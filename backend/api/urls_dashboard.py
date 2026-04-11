"""
Dashboard URLs: ParkPe summary, pincode.
Mount at /api/dashboard/
"""
from django.urls import path, include

urlpatterns = [
    path("", include("api.parkpe_api.urls")),
]
