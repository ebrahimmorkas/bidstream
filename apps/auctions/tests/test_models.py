from decimal import Decimal

import pytest
from django.db import IntegrityError

from apps.auctions.models import Auction
from apps.auctions.tests.factories import AuctionFactory

pytestmark = pytest.mark.django_db


def test_phases():
    assert AuctionFactory().phase == "live"
    assert AuctionFactory(upcoming=True).phase == "upcoming"
    assert AuctionFactory(expired=True).phase == "ending"
    assert AuctionFactory(status=Auction.Status.CANCELLED).phase == "cancelled"


def test_querysets_partition_auctions():
    live = AuctionFactory()
    upcoming = AuctionFactory(upcoming=True)
    expired = AuctionFactory(expired=True)

    assert list(Auction.objects.live()) == [live]
    assert list(Auction.objects.upcoming()) == [upcoming]
    assert list(Auction.objects.due_for_closing()) == [expired]


def test_minimum_next_bid():
    auction = AuctionFactory(starting_price=Decimal("10.00"), min_increment=Decimal("2.50"))
    assert auction.minimum_next_bid == Decimal("10.00")

    auction.current_price = Decimal("12.00")
    assert auction.minimum_next_bid == Decimal("14.50")


def test_reserve_met():
    auction = AuctionFactory(reserve_price=Decimal("50.00"))
    assert not auction.reserve_met

    auction.current_price = Decimal("50.00")
    assert auction.reserve_met
    assert AuctionFactory().reserve_met  # no reserve


def test_reserve_cannot_be_below_starting_price():
    with pytest.raises(IntegrityError):
        AuctionFactory(starting_price=Decimal("10"), reserve_price=Decimal("5"))
