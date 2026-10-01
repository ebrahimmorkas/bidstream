from decimal import Decimal

import pytest
from django.core import mail

from apps.accounts.tests.factories import UserFactory
from apps.auctions.tests.factories import AuctionFactory
from apps.bidding.services import place_bid

pytestmark = pytest.mark.django_db


def test_previous_leader_is_emailed_when_outbid(django_capture_on_commit_callbacks):
    auction = AuctionFactory(title="Gibson Les Paul")
    first, second = UserFactory(), UserFactory()

    with django_capture_on_commit_callbacks(execute=True):
        place_bid(auction_id=auction.pk, bidder=first, amount=Decimal("100"))
    assert mail.outbox == []  # nobody to notify for the first bid

    with django_capture_on_commit_callbacks(execute=True):
        place_bid(auction_id=auction.pk, bidder=second, amount=Decimal("150"))

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [first.email]
    assert message.subject == "You've been outbid on Gibson Les Paul"
    assert "$150.00" in message.body
    assert f"/auctions/{auction.pk}/" in message.body
