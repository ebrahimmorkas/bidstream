from django.urls import path

from . import views

app_name = "auctions"

urlpatterns = [
    path("", views.AuctionListView.as_view(), name="list"),
    path("new/", views.AuctionCreateView.as_view(), name="create"),
    path("mine/", views.MyListingsView.as_view(), name="mine"),
    path("watchlist/", views.WatchlistView.as_view(), name="watchlist"),
    path("<int:pk>/", views.AuctionDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.AuctionUpdateView.as_view(), name="edit"),
    path("<int:pk>/cancel/", views.AuctionCancelView.as_view(), name="cancel"),
    path("<int:pk>/watch/", views.ToggleWatchView.as_view(), name="watch"),
]
