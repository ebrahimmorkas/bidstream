from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.auctions.models import Auction

from .groups import FEED_GROUP, auction_group

CLOSE_NOT_FOUND = 4404


class PushConsumer(AsyncJsonWebsocketConsumer):
    """Read-only stream: clients subscribe to a group and receive pushed events.

    Bids are placed over HTTP (validated, rate-limitable, CSRF protected); the
    socket is only used for fan-out, which keeps the consumers trivial to scale.
    """

    group_name: str

    async def disconnect(self, code):
        if getattr(self, "group_name", None):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def push(self, event):
        await self.send_json(event["payload"])


class AuctionConsumer(PushConsumer):
    """Live updates for a single auction page."""

    async def connect(self):
        auction_id = self.scope["url_route"]["kwargs"]["auction_id"]
        if not await self._auction_exists(auction_id):
            await self.close(code=CLOSE_NOT_FOUND)
            return
        self.group_name = auction_group(auction_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    @database_sync_to_async
    def _auction_exists(self, auction_id: int) -> bool:
        return Auction.objects.filter(pk=auction_id).exists()


class FeedConsumer(PushConsumer):
    """Price ticker for listing pages: every bid on every auction."""

    async def connect(self):
        self.group_name = FEED_GROUP
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
