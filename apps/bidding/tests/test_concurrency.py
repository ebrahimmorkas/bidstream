"""Race-condition test: many bidders submit the same amount at the same instant.

Row-level locks are only meaningful on PostgreSQL, so this test is skipped on SQLite.
CI runs the suite against PostgreSQL as well.
"""

import threading
from decimal import Decimal

import pytest
from django.db import connection, connections

from apps.accounts.tests.factories import UserFactory
from apps.auctions.models import Auction
from apps.auctions.tests.factories import AuctionFactory
from apps.bidding.models import Bid
from apps.bidding.services import BidRejected, place_bid

pytestmark = pytest.mark.skipif(
    connection.vendor != "postgresql", reason="requires PostgreSQL row-level locking"
)


@pytest.mark.django_db(transaction=True)
def test_concurrent_identical_bids_only_one_wins():
    auction = AuctionFactory(starting_price=Decimal("100.00"))
    bidders = [UserFactory() for _ in range(10)]
    barrier = threading.Barrier(len(bidders))
    accepted: list[int] = []
    rejected: list[int] = []

    def attempt(user):
        try:
            barrier.wait()
            place_bid(auction_id=auction.pk, bidder=user, amount=Decimal("100.00"))
            accepted.append(user.pk)
        except BidRejected:
            rejected.append(user.pk)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=attempt, args=(u,)) for u in bidders]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    auction = Auction.objects.get(pk=auction.pk)
    assert len(accepted) == 1
    assert len(rejected) == len(bidders) - 1
    assert auction.bid_count == Bid.objects.count() == 1
    assert auction.leading_bidder_id == accepted[0]
