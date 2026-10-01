from decimal import Decimal

import pytest
from asgiref.sync import sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.db import transaction

from apps.accounts.tests.factories import UserFactory
from apps.auctions.tests.factories import AuctionFactory
from apps.bidding.services import place_bid
from apps.realtime.broadcast import broadcast_auction_closed
from apps.realtime.routing import websocket_urlpatterns

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]

application = URLRouter(websocket_urlpatterns)


async def connect(path: str) -> WebsocketCommunicator:
    communicator = WebsocketCommunicator(application, path)
    connected, _ = await communicator.connect()
    assert connected
    return communicator


@sync_to_async
def create_auction(**kwargs):
    return AuctionFactory(**kwargs)


@sync_to_async
def bid(auction, amount, display_name="johnny"):
    # transaction.atomic + commit makes on_commit hooks (the broadcast) fire.
    with transaction.atomic():
        user = UserFactory(display_name=display_name)
        return place_bid(auction_id=auction.pk, bidder=user, amount=Decimal(amount))


async def test_unknown_auction_is_rejected():
    communicator = WebsocketCommunicator(application, "/ws/auctions/999999/")
    connected, code = await communicator.connect()

    assert not connected
    assert code == 4404


async def test_ping_pong():
    auction = await create_auction()
    communicator = await connect(f"/ws/auctions/{auction.pk}/")

    await communicator.send_json_to({"type": "ping"})

    assert await communicator.receive_json_from() == {"type": "pong"}
    await communicator.disconnect()


async def test_bid_is_pushed_to_auction_subscribers():
    auction = await create_auction(starting_price=Decimal("10.00"))
    communicator = await connect(f"/ws/auctions/{auction.pk}/")

    await bid(auction, "1250.00")
    message = await communicator.receive_json_from(timeout=2)

    assert message["type"] == "bid"
    assert message["amount"] == "1,250.00"
    assert message["bidder"] == "j***y"
    assert message["bid_count"] == 1
    assert message["minimum_next_bid"] == "1251.00"
    await communicator.disconnect()


async def test_subscribers_of_other_auctions_receive_nothing():
    watched, other = await create_auction(), await create_auction()
    communicator = await connect(f"/ws/auctions/{watched.pk}/")

    await bid(other, "50.00")

    assert await communicator.receive_nothing(timeout=0.3)
    await communicator.disconnect()


async def test_feed_receives_bids_for_all_auctions():
    first, second = await create_auction(), await create_auction()
    feed = await connect("/ws/feed/")

    await bid(first, "20.00", "alice")
    await bid(second, "30.00", "bobby")

    ids = {(await feed.receive_json_from(timeout=2))["auction_id"] for _ in range(2)}
    assert ids == {first.pk, second.pk}
    await feed.disconnect()


async def test_closed_event_is_pushed():
    auction = await create_auction()
    communicator = await connect(f"/ws/auctions/{auction.pk}/")

    await sync_to_async(broadcast_auction_closed)(auction)
    message = await communicator.receive_json_from(timeout=2)

    assert message == {
        "type": "closed",
        "auction_id": auction.pk,
        "sold": False,
        "winner_id": None,
        "winner": None,
        "final_price": None,
    }
    await communicator.disconnect()
