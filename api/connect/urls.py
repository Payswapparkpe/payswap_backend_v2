"""
ParkPe Connect API – URL config. Base path: /api/connect/
"""
from django.urls import path
from . import views

urlpatterns = [
    path('vehicles/', views.VehicleListCreateView.as_view(), name='connect-vehicles-list-create'),
    path('vehicles/<int:pk>/', views.VehicleDetailView.as_view(), name='connect-vehicle-detail'),
    path('vehicles/<int:pk>/qr/', views.VehicleQRView.as_view(), name='connect-vehicle-qr'),
    path('vehicle/by-qr/<str:qr_code>/', views.VehicleByQRView.as_view(), name='connect-vehicle-by-qr'),
    path('vehicle/by-registration/<str:registration_number>/', views.VehicleByRegistrationView.as_view(), name='connect-vehicle-by-registration'),
    path('call/initiate/', views.ConnectCallInitiateView.as_view(), name='connect-call-initiate'),
]
