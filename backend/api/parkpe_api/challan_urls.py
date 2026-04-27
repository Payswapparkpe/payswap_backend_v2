from django.urls import path

from .views import ChallanSearchView, ChallanDetailView, ChallanPayView

urlpatterns = [
    path("search", ChallanSearchView.as_view(), name="parkpe-challan-search"),
    path("<str:challan_id>", ChallanDetailView.as_view(), name="parkpe-challan-detail"),
    path("<str:challan_id>/pay", ChallanPayView.as_view(), name="parkpe-challan-pay"),
]
