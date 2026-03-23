from django.urls import path
from .views import DashboardSummaryView, PincodeLookupView

urlpatterns = [
    path("summary", DashboardSummaryView.as_view(), name="parkpe-dashboard-summary"),
    path("pincode", PincodeLookupView.as_view(), name="parkpe-pincode-lookup"),
]
