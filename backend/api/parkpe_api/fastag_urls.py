from django.urls import path

from .views import FastagRechargeView

urlpatterns = [
    path("recharge", FastagRechargeView.as_view(), name="parkpe-fastag-recharge"),
]
