from django.urls import path
from .views import (
    BBPSCategoriesView,
    BBPSOperatorsView,
    BBPSFetchBillView,
    BBPSPayBillView,
    BBPSPayCartView,
    BBPSFavoritesListView,
    BBPSFavoriteDeleteView,
    BBPSSavedBillsListView,
    BBPSSavedBillUpdateView,
    BBPSSavedBillDeleteView,
)

urlpatterns = [
    path("categories", BBPSCategoriesView.as_view(), name="bbps-parkpe-categories"),
    path("operators", BBPSOperatorsView.as_view(), name="bbps-parkpe-operators"),
    path("fetch-bill", BBPSFetchBillView.as_view(), name="bbps-parkpe-fetch-bill"),
    path("pay", BBPSPayBillView.as_view(), name="bbps-parkpe-pay"),
    path("pay-cart", BBPSPayCartView.as_view(), name="bbps-parkpe-pay-cart"),
    path("favorites", BBPSFavoritesListView.as_view(), name="bbps-parkpe-favorites-list"),
    path("favorites/<str:operator_id>", BBPSFavoriteDeleteView.as_view(), name="bbps-parkpe-favorite-delete"),
    path("saved-bills", BBPSSavedBillsListView.as_view(), name="bbps-parkpe-saved-bills-list"),
    path("saved-bills/<int:pk>", BBPSSavedBillUpdateView.as_view(), name="bbps-parkpe-saved-bill-update"),
    path("saved-bills/<int:pk>/delete", BBPSSavedBillDeleteView.as_view(), name="bbps-parkpe-saved-bill-delete"),
]
