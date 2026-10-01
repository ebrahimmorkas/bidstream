from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.auctions.models import Auction
from apps.auctions.tests.factories import AuctionFactory
from apps.bidding.models import Bid
from apps.bidding.services import BidRejected, parse_amount, place_bid
from apps.bidding.signals import bid_placed

pytestmark = pytest.mark.django_db


@pytest.fixture
def auction():
    return AuctionFactory(starting_price=Decimal("10.00"), min_increment=Decimal("1.00"))


def bid(auction, user, amount):
    return place_bid(auction_id=auction.pk, bidder=user, amount=Decimal(amount))


def test_first_bid_can_equal_starting_price(auction):
    result = bid(auction, UserFactory(), "10.00")

    auction.refresh_from_db()
    assert auction.current_price == Decimal("10.00")
    assert auction.bid_count == 1
    assert auction.leading_bidder == result.bid.bidder


def test_subsequent_bids_must_beat_price_by_increment(auction):
    bid(auction, UserFactory(), "10.00")

    with pytest.raises(BidRejected, match=r"at least \$11.00"):
        bid(auction, UserFactory(), "10.50")


def test_seller_cannot_bid(auction):
    with pytest.raises(BidRejected, match="own auction"):
        bid(auction, auction.seller, "20.00")


def test_leader_cannot_outbid_themselves(auction):
    user = UserFactory()
    bid(auction, user, "10.00")

    with pytest.raises(BidRejected, match="already the highest"):
        bid(auction, user, "15.00")


@pytest.mark.parametrize("trait", ["upcoming", "expired"])
def test_cannot_bid_outside_live_window(trait):
    auction = AuctionFactory(**{trait: True})

    with pytest.raises(BidRejected, match="not accepting"):
        bid(auction, UserFactory(), "100.00")


def test_cannot_bid_on_cancelled_auction():
    auction = AuctionFactory(status=Auction.Status.CANCELLED)

    with pytest.raises(BidRejected):
        bid(auction, UserFactory(), "100.00")


def test_max_bid_limit(auction, settings):
    settings.BIDSTREAM_MAX_BID = Decimal("500")

    with pytest.raises(BidRejected, match="cannot exceed"):
        bid(auction, UserFactory(), "500.01")


def test_late_bid_extends_auction(settings):
    settings.BIDSTREAM_ANTI_SNIPE_MINUTES = 2
    auction = AuctionFactory(ends_at=timezone.now() + timedelta(seconds=30))

    result = bid(auction, UserFactory(), "10.00")

    assert result.extended
    auction.refresh_from_db()
    assert auction.ends_at >= timezone.now() + timedelta(seconds=110)


def test_early_bid_does_not_extend(auction):
    original_end = auction.ends_at

    assert not bid(auction, UserFactory(), "10.00").extended
    auction.refresh_from_db()
    assert auction.ends_at == original_end


def test_bid_placed_signal_fires_after_commit(auction, django_capture_on_commit_callbacks):
    first, second = UserFactory(), UserFactory()
    received = []

    def receiver(**kwargs):
        received.append(kwargs)

    bid_placed.connect(receiver)
    try:
        bid(auction, first, "10.00")
        with django_capture_on_commit_callbacks(execute=True):
            bid(auction, second, "12.00")
    finally:
        bid_placed.disconnect(receiver)

    assert len(received) == 1  # only the bid whose commit callbacks ran
    assert received[0]["previous_leader_id"] == first.pk
    assert received[0]["bid"].amount == Decimal("12.00")


@pytest.mark.parametrize(
    ("raw", "expected"), [("12", Decimal("12")), ("1,250.50", Decimal("1250.50"))]
)
def test_parse_amount_accepts_valid_input(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "-5", "0", "10.001", "NaN", "Infinity"])
def test_parse_amount_rejects_invalid_input(raw):
    with pytest.raises(BidRejected):
        parse_amount(raw)


def test_bids_are_ordered_highest_first(auction):
    bid(auction, UserFactory(), "10.00")
    bid(auction, UserFactory(), "15.00")

    assert [b.amount for b in Bid.objects.all()] == [Decimal("15.00"), Decimal("10.00")]
