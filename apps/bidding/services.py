"""Bid placement.

Concurrency: the auction row is locked with ``SELECT ... FOR UPDATE`` for the
duration of the transaction, so two simultaneous bids are applied one after the
other and the second is validated against the price set by the first. A unique
constraint on (auction, amount) acts as a last line of defence.

Anti-sniping: a bid in the final ``BIDSTREAM_ANTI_SNIPE_MINUTES`` pushes the end
time out so other bidders always get a chance to respond.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.auctions.models import Auction

from .models import Bid
from .signals import bid_placed

CENT = Decimal("0.01")


class BidRejected(Exception):
    """A bid violated an auction rule. The message is safe to show to users."""


@dataclass(frozen=True)
class BidResult:
    bid: Bid
    auction: Auction
    extended: bool


def parse_amount(raw) -> Decimal:
    try:
        amount = Decimal(str(raw).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        raise BidRejected("Enter a valid amount.") from None
    if not amount.is_finite() or amount <= 0:
        raise BidRejected("Enter a valid amount.")
    if amount != amount.quantize(CENT):
        raise BidRejected("Bids can have at most two decimal places.")
    return amount


@transaction.atomic
def place_bid(*, auction_id: int, bidder, amount: Decimal) -> BidResult:
    auction = Auction.objects.select_for_update().get(pk=auction_id)
    now = timezone.now()

    if auction.phase != "live":
        raise BidRejected("This auction is not accepting bids.")
    if auction.seller_id == bidder.pk:
        raise BidRejected("You cannot bid on your own auction.")
    if auction.leading_bidder_id == bidder.pk:
        raise BidRejected("You are already the highest bidder.")
    if amount < auction.minimum_next_bid:
        raise BidRejected(f"Your bid must be at least ${auction.minimum_next_bid:,.2f}.")
    if amount > settings.BIDSTREAM_MAX_BID:
        raise BidRejected(f"Bids cannot exceed ${settings.BIDSTREAM_MAX_BID:,.2f}.")

    previous_leader_id = auction.leading_bidder_id
    bid = Bid.objects.create(auction=auction, bidder=bidder, amount=amount)

    auction.current_price = amount
    auction.bid_count += 1
    auction.leading_bidder = bidder

    window = timedelta(minutes=settings.BIDSTREAM_ANTI_SNIPE_MINUTES)
    extended = auction.ends_at - now < window
    if extended:
        auction.ends_at = now + window

    auction.save(
        update_fields=["current_price", "bid_count", "leading_bidder", "ends_at", "updated_at"]
    )

    transaction.on_commit(
        lambda: bid_placed.send(
            sender=Bid,
            bid=bid,
            auction=auction,
            previous_leader_id=previous_leader_id,
            extended=extended,
        )
    )
    return BidResult(bid=bid, auction=auction, extended=extended)
