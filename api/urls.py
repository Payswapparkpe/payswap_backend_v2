"""
API URL Configuration with Versioning
- v1: Internal access (staff/authenticated users)
- v2: External parties (public/API keys)
"""
from django.urls import path, include

urlpatterns = [
    path("v1/", include("api.v1.urls")),  # Internal API
    path("v2/", include("api.v2.urls")),  # External API
]
