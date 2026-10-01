from django.urls import path

from .consumers import AuctionConsumer, FeedConsumer

websocket_urlpatterns = [
    path("ws/auctions/<int:auction_id>/", AuctionConsumer.as_asgi()),
    path("ws/feed/", FeedConsumer.as_asgi()),
]
