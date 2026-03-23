from django.urls import path
from .views import InternalHealthView, InternalRunJobView

urlpatterns = [
    path("health/", InternalHealthView.as_view(), name="internal-health"),
    path("run-job/", InternalRunJobView.as_view(), name="internal-run-job"),
]
