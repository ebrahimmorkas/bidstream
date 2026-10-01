from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory
from apps.auctions.tests.factories import AuctionFactory
from apps.bidding.models import Bid
from apps.bidding.services import place_bid

pytestmark = pytest.mark.django_db


@pytest.fixture
def bidder(client):
    user = UserFactory()
    client.force_login(user)
    return user


def test_bid_requires_login(client):
    auction = AuctionFactory()

    response = client.post(reverse("bidding:place", args=[auction.pk]), {"amount": "20"})

    assert response.status_code == 302
    assert not Bid.objects.exists()


def test_htmx_bid_returns_updated_panel(client, bidder):
    auction = AuctionFactory()

    response = client.post(
        reverse("bidding:place", args=[auction.pk]),
        {"amount": "25.00"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert b'id="bid-panel"' in response.content
    assert b"You are the highest bidder" in response.content
    assert Bid.objects.get().bidder == bidder


def test_htmx_bid_error_is_rendered_in_panel(client, bidder):
    auction = AuctionFactory(starting_price=Decimal("50"))

    response = client.post(
        reverse("bidding:place", args=[auction.pk]),
        {"amount": "10"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert b"at least $50.00" in response.content
    assert not Bid.objects.exists()


def test_regular_post_redirects_with_message(client, bidder):
    auction = AuctionFactory()

    response = client.post(
        reverse("bidding:place", args=[auction.pk]), {"amount": "garbage"}, follow=True
    )

    assert response.redirect_chain[-1][0] == auction.get_absolute_url()
    assert "Enter a valid amount." in [str(m) for m in response.context["messages"]]


def test_detail_page_shows_bid_history_with_masked_names(client):
    auction = AuctionFactory()
    place_bid(auction_id=auction.pk, bidder=UserFactory(display_name="johnny"), amount=Decimal(10))

    response = client.get(auction.get_absolute_url())

    assert b"j***y" in response.content
    assert b"johnny" not in response.content


def test_my_bids_shows_leading_and_outbid(client, bidder):
    leading = AuctionFactory(title="Leading item")
    outbid = AuctionFactory(title="Outbid item")
    place_bid(auction_id=leading.pk, bidder=bidder, amount=Decimal(10))
    place_bid(auction_id=outbid.pk, bidder=bidder, amount=Decimal(10))
    place_bid(auction_id=outbid.pk, bidder=UserFactory(), amount=Decimal(20))

    content = client.get(reverse("bidding:mine")).content.decode()

    assert "Leading item" in content and "Outbid item" in content
    assert "Leading</span>" in content and "Outbid</span>" in content
