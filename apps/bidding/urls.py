from django.urls import path

from . import views

app_name = "bidding"

urlpatterns = [
    path("auctions/<int:pk>/bid/", views.place_bid_view, name="place"),
    path("my-bids/", views.MyBidsView.as_view(), name="mine"),
]
