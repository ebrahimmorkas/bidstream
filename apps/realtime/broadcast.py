"""Push domain events to WebSocket clients through the channel layer.

With Redis configured the channel layer fans messages out across every Daphne
process; without it the in-memory layer works for a single development process.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .groups import FEED_GROUP, auction_group

logger = logging.getLogger(__name__)


def _money(value) -> str:
    return f"{value:,.2f}"


def bid_payload(bid, auction, extended: bool) -> dict:
    return {
        "type": "bid",
        "auction_id": auction.pk,
        "amount": _money(bid.amount),
        "bidder": bid.bidder.masked_name,
        "leader_id": auction.leading_bidder_id,
        "current_price": _money(auction.current_price),
        "minimum_next_bid": str(auction.minimum_next_bid),
        "minimum_next_bid_display": _money(auction.minimum_next_bid),
        "bid_count": auction.bid_count,
        "ends_at": auction.ends_at.isoformat(),
        "extended": extended,
    }


def send_to_groups(payload: dict, *groups: str) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    for group in groups:
        try:
            async_to_sync(layer.group_send)(group, {"type": "push", "payload": payload})
        except Exception:  # broadcasting must never break the request that placed the bid
            logger.exception("Failed to broadcast to %s", group)


def on_bid_placed(sender, bid, auction, extended, **kwargs) -> None:
    send_to_groups(bid_payload(bid, auction, extended), auction_group(auction.pk), FEED_GROUP)


def broadcast_auction_closed(auction) -> None:
    payload = {
        "type": "closed",
        "auction_id": auction.pk,
        "sold": auction.winner_id is not None,
        "winner_id": auction.winner_id,
        "winner": auction.winner.masked_name if auction.winner_id else None,
        "final_price": _money(auction.current_price) if auction.current_price else None,
    }
    send_to_groups(payload, auction_group(auction.pk), FEED_GROUP)
