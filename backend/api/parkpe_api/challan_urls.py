from django.urls import path

from .views import (
    ChallanSearchView,
    ChallanDetailView,
    ChallanPayView,
    ChallanHistoryView,
    ChallanReceiptView,
    ChallanSavedVehiclesView,
    ChallanSavedVehicleDeleteView,
)

urlpatterns = [
    path("search", ChallanSearchView.as_view(), name="parkpe-challan-search"),
    path("history", ChallanHistoryView.as_view(), name="parkpe-challan-history"),
    path("vehicles", ChallanSavedVehiclesView.as_view(), name="parkpe-challan-saved-vehicles"),
    path("vehicles/<int:vehicle_id>", ChallanSavedVehicleDeleteView.as_view(), name="parkpe-challan-saved-vehicle-delete"),
    path("<str:challan_id>", ChallanDetailView.as_view(), name="parkpe-challan-detail"),
    path("<str:challan_id>/pay", ChallanPayView.as_view(), name="parkpe-challan-pay"),
    path("<str:challan_id>/receipt", ChallanReceiptView.as_view(), name="parkpe-challan-receipt"),
]
