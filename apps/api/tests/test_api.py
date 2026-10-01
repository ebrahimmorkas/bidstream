from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory
from apps.auctions.models import Auction
from apps.auctions.tests.factories import AuctionFactory, CategoryFactory
from apps.bidding.models import Bid

pytestmark = pytest.mark.django_db


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def token_api(api, user):
    token = api.post(
        reverse("api:token"), {"username": user.email, "password": DEFAULT_PASSWORD}
    ).json()["token"]
    api.credentials(HTTP_AUTHORIZATION=f"Token {token}")
    return api


def test_list_excludes_cancelled_and_supports_phase_filter(api):
    live = AuctionFactory()
    AuctionFactory(upcoming=True)
    AuctionFactory(status=Auction.Status.CANCELLED)

    all_ids = [a["id"] for a in api.get(reverse("api:auction-list")).json()["results"]]
    live_ids = [
        a["id"] for a in api.get(reverse("api:auction-list"), {"phase": "live"}).json()["results"]
    ]

    assert len(all_ids) == 2
    assert live_ids == [live.pk]


def test_filter_by_category_and_price(api):
    art = CategoryFactory(slug="art", name="Art")
    match = AuctionFactory(category=art, starting_price=Decimal("50"))
    AuctionFactory(category=art, starting_price=Decimal("500"))

    response = api.get(reverse("api:auction-list"), {"category": "art", "max_price": 100})

    assert [a["id"] for a in response.json()["results"]] == [match.pk]


def test_detail_exposes_computed_fields(api):
    auction = AuctionFactory(starting_price=Decimal("10"), reserve_price=Decimal("20"))

    body = api.get(reverse("api:auction-detail", args=[auction.pk])).json()

    assert body["phase"] == "live"
    assert body["minimum_next_bid"] == "10.00"
    assert body["reserve_met"] is False
    assert "reserve_price" not in body  # reserve stays secret


def test_place_bid_with_token(token_api, user):
    auction = AuctionFactory()

    response = token_api.post(
        reverse("api:auction-bids", args=[auction.pk]), {"amount": "42.50"}, format="json"
    )

    assert response.status_code == 201
    assert response.json()["amount"] == "42.50"
    assert Bid.objects.get().bidder == user


def test_rejected_bid_returns_409(token_api):
    auction = AuctionFactory(starting_price=Decimal("100"))

    response = token_api.post(
        reverse("api:auction-bids", args=[auction.pk]), {"amount": "5"}, format="json"
    )

    assert response.status_code == 409
    assert response.json()["code"] == "bid_rejected"


def test_anonymous_cannot_bid_but_can_read_bids(api):
    auction = AuctionFactory()
    url = reverse("api:auction-bids", args=[auction.pk])

    assert api.post(url, {"amount": "50"}, format="json").status_code == 401
    assert api.get(url).status_code == 200


def test_bid_history_masks_bidders(token_api, api):
    auction = AuctionFactory()
    token_api.post(reverse("api:auction-bids", args=[auction.pk]), {"amount": "20"}, format="json")

    bids = api.get(reverse("api:auction-bids", args=[auction.pk])).json()["results"]

    assert "*" in bids[0]["bidder"]


def test_openapi_schema(api):
    response = api.get(reverse("api:schema"))

    assert response.status_code == 200
    assert b"/api/v1/auctions/{id}/bids/" in response.content
