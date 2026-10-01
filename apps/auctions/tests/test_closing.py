from datetime import timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.auctions.models import Auction
from apps.auctions.services import close_auction, close_due_auctions
from apps.auctions.tasks import close_expired_auctions
from apps.auctions.tests.factories import AuctionFactory

pytestmark = pytest.mark.django_db


def expired_with_leader(price="25.00", **kwargs):
    leader = UserFactory()
    return AuctionFactory(
        expired=True,
        leading_bidder=leader,
        current_price=Decimal(price),
        bid_count=3,
        **kwargs,
    )


def test_close_sets_winner_to_leading_bidder():
    auction = expired_with_leader()

    closed = close_auction(auction.pk)

    assert closed is not None
    auction.refresh_from_db()
    assert auction.status == Auction.Status.CLOSED
    assert auction.winner == auction.leading_bidder
    assert auction.closed_at is not None


def test_reserve_not_met_means_no_winner():
    auction = expired_with_leader(price="40.00", reserve_price=Decimal("50.00"))

    close_auction(auction.pk)

    auction.refresh_from_db()
    assert auction.status == Auction.Status.CLOSED
    assert auction.winner is None


def test_live_auction_is_not_closed():
    auction = AuctionFactory()

    assert close_auction(auction.pk) is None
    auction.refresh_from_db()
    assert auction.status == Auction.Status.OPEN


def test_closing_is_idempotent():
    auction = expired_with_leader()

    assert close_auction(auction.pk) is not None
    assert close_auction(auction.pk) is None


def test_close_due_auctions_only_touches_expired():
    expired = [AuctionFactory(expired=True) for _ in range(3)]
    live = AuctionFactory()

    assert close_due_auctions() == 3
    assert close_expired_auctions() == 0  # Celery task wrapper; nothing left to close
    assert all(Auction.objects.get(pk=a.pk).status == Auction.Status.CLOSED for a in expired)
    assert Auction.objects.get(pk=live.pk).status == Auction.Status.OPEN


def test_management_command(capsys):
    AuctionFactory(expired=True)

    call_command("close_auctions")

    assert "Closed 1 auction(s)." in capsys.readouterr().out


def test_viewing_expired_auction_closes_it_lazily(client):
    auction = expired_with_leader()

    response = client.get(auction.get_absolute_url())

    assert b"Won by" in response.content
    auction.refresh_from_db()
    assert auction.status == Auction.Status.CLOSED


def test_results_emails_sent_after_commit(django_capture_on_commit_callbacks):
    auction = expired_with_leader()

    with django_capture_on_commit_callbacks(execute=True):
        close_auction(auction.pk)

    by_recipient = {m.to[0]: m for m in mail.outbox}
    assert set(by_recipient) == {auction.seller.email, auction.leading_bidder.email}
    assert "Sold for $25.00" in by_recipient[auction.seller.email].body
    assert by_recipient[auction.leading_bidder.email].subject.startswith("You won")


def test_unsold_auction_only_emails_seller(django_capture_on_commit_callbacks):
    auction = AuctionFactory(expired=True)

    with django_capture_on_commit_callbacks(execute=True):
        close_auction(auction.pk)

    assert [m.to for m in mail.outbox] == [[auction.seller.email]]
    assert "no bids" in mail.outbox[0].body


def test_extended_auction_is_not_closed_by_stale_selection():
    auction = AuctionFactory(ends_at=timezone.now() + timedelta(minutes=2))

    assert close_auction(auction.pk) is None
