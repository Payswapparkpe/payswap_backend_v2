"""
ParkPe Connect API – URL config. Base path: /api/connect/
"""
from django.urls import path
from . import views

urlpatterns = [
    path('vehicles/', views.VehicleListCreateView.as_view(), name='connect-vehicles-list-create'),
    path('vehicles/<int:pk>/', views.VehicleDetailView.as_view(), name='connect-vehicle-detail'),
    path('vehicles/<int:pk>/delete-request/', views.VehicleDeleteRequestView.as_view(), name='connect-vehicle-delete-request'),
    path('vehicles/<int:pk>/delete/', views.VehicleDeleteConfirmView.as_view(), name='connect-vehicle-delete-confirm'),
    path('vehicles/<int:pk>/unlock-rc/', views.VehicleUnlockRCView.as_view(), name='connect-vehicle-unlock-rc'),
    path('vehicles/<int:pk>/pay-rc-view/', views.VehiclePayRCView.as_view(), name='connect-vehicle-pay-rc-view'),
    path('vehicles/<int:pk>/fetch-rc/', views.VehicleFetchRCView.as_view(), name='connect-vehicle-fetch-rc'),
    path('vehicles/<int:pk>/qr/', views.VehicleQRView.as_view(), name='connect-vehicle-qr'),
    path('vehicle/by-qr/<str:qr_code>/', views.VehicleByQRView.as_view(), name='connect-vehicle-by-qr'),
    path('vehicle/by-registration/<str:registration_number>/', views.VehicleByRegistrationView.as_view(), name='connect-vehicle-by-registration'),
    path('call/token/', views.ConnectCallTokenView.as_view(), name='connect-call-token'),
    path('call/initiate/', views.ConnectCallInitiateView.as_view(), name='connect-call-initiate'),
    path('scanner/send-otp/', views.ConnectScannerSendOTPView.as_view(), name='connect-scanner-send-otp'),
    path('scanner/verify-otp/', views.ConnectScannerVerifyOTPView.as_view(), name='connect-scanner-verify-otp'),
    path('chat/predefined-messages/', views.ConnectPredefinedMessagesView.as_view(), name='connect-chat-predefined-messages'),
    path('chat/threads/', views.ConnectThreadListCreateView.as_view(), name='connect-chat-threads'),
    path('chat/threads/<int:pk>/', views.ConnectThreadDetailView.as_view(), name='connect-chat-thread-detail'),
    path('chat/threads/<int:pk>/messages/', views.ConnectThreadMessagesView.as_view(), name='connect-chat-thread-messages'),
    path('report/', views.ConnectReportCreateView.as_view(), name='connect-report-create'),
]
