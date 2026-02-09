from django.urls import path
from .views import (
    BBPSCategoriesView,
    BBPSOperatorsView,
    BBPSFetchBillView,
    BBPSPayBillView,
)

urlpatterns = [
    path("categories", BBPSCategoriesView.as_view(), name="bbps-parkpe-categories"),
    path("operators", BBPSOperatorsView.as_view(), name="bbps-parkpe-operators"),
    path("fetch-bill", BBPSFetchBillView.as_view(), name="bbps-parkpe-fetch-bill"),
    path("pay", BBPSPayBillView.as_view(), name="bbps-parkpe-pay"),
]
