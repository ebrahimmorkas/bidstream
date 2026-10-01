from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.auctions.models import Auction, Watch
from apps.auctions.tests.factories import AuctionFactory, CategoryFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client


def local_input(dt):
    return dt.strftime("%Y-%m-%dT%H:%M")


def auction_payload(**overrides):
    now = timezone.now()
    data = {
        "title": "Leica M6",
        "description": "Film camera, mint condition.",
        "starting_price": "500.00",
        "min_increment": "10.00",
        "reserve_price": "",
        "starts_at": local_input(now),
        "ends_at": local_input(now + timedelta(days=3)),
    }
    data.update(overrides)
    return data


def test_list_shows_live_auctions_by_default(client):
    live = AuctionFactory(title="Live one")
    AuctionFactory(title="Upcoming one", upcoming=True)

    response = client.get(reverse("auctions:list"))

    assert list(response.context["auctions"]) == [live]


def test_list_filters_by_search_category_and_phase(client):
    cameras = CategoryFactory(name="Cameras", slug="cameras")
    match = AuctionFactory(title="Leica camera", category=cameras, upcoming=True)
    AuctionFactory(title="Leica lens", upcoming=True)
    AuctionFactory(title="Nikon camera", category=cameras, upcoming=True)

    response = client.get(
        reverse("auctions:list"), {"q": "leica", "category": "cameras", "phase": "upcoming"}
    )

    assert list(response.context["auctions"]) == [match]


def test_list_sorts_by_effective_price(client):
    cheap = AuctionFactory(starting_price=Decimal("5"))
    bid_up = AuctionFactory(starting_price=Decimal("1"), current_price=Decimal("50"))

    response = client.get(reverse("auctions:list"), {"sort": "price_desc"})

    assert list(response.context["auctions"]) == [bid_up, cheap]


def test_htmx_request_returns_results_fragment(client):
    AuctionFactory()

    response = client.get(reverse("auctions:list"), headers={"HX-Request": "true"})

    assert [t.name for t in response.templates][0] == "auctions/_results.html"
    assert b"<html" not in response.content


def test_detail_page(client):
    auction = AuctionFactory(title="Signed vinyl")

    response = client.get(auction.get_absolute_url())

    assert response.status_code == 200
    assert b"Signed vinyl" in response.content


def test_create_requires_login(client):
    response = client.get(reverse("auctions:create"))

    assert response.status_code == 302
    assert reverse("login") in response.url


def test_create_auction(auth_client, user):
    response = auth_client.post(reverse("auctions:create"), auction_payload())

    auction = Auction.objects.get()
    assert response.status_code == 302
    assert auction.seller == user
    assert auction.status == Auction.Status.OPEN


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"ends_at": local_input(timezone.now() + timedelta(minutes=2))}, "ends_at"),
        ({"ends_at": local_input(timezone.now() + timedelta(days=60))}, "ends_at"),
        ({"starts_at": local_input(timezone.now() - timedelta(days=1))}, "starts_at"),
        ({"reserve_price": "100.00"}, "reserve_price"),
    ],
)
def test_create_validation(auth_client, overrides, field):
    response = auth_client.post(reverse("auctions:create"), auction_payload(**overrides))

    assert response.status_code == 200
    assert field in response.context["form"].errors


def test_seller_can_edit_before_bids(auth_client, user):
    auction = AuctionFactory(seller=user)

    response = auth_client.post(
        reverse("auctions:edit", args=[auction.pk]),
        auction_payload(title="Renamed", starts_at=local_input(auction.starts_at)),
    )

    assert response.status_code == 302
    auction.refresh_from_db()
    assert auction.title == "Renamed"


def test_cannot_edit_after_bidding_started(auth_client, user):
    auction = AuctionFactory(seller=user, bid_count=1, current_price=Decimal("11"))

    response = auth_client.get(reverse("auctions:edit", args=[auction.pk]))

    assert response.status_code == 403


def test_cannot_edit_someone_elses_auction(auth_client):
    auction = AuctionFactory()

    assert auth_client.get(reverse("auctions:edit", args=[auction.pk])).status_code == 404


def test_seller_cancels_auction(auth_client, user):
    auction = AuctionFactory(seller=user)

    auth_client.post(reverse("auctions:cancel", args=[auction.pk]))

    auction.refresh_from_db()
    assert auction.status == Auction.Status.CANCELLED


def test_toggle_watch_with_htmx(auth_client, user):
    auction = AuctionFactory()
    url = reverse("auctions:watch", args=[auction.pk])

    first = auth_client.post(url, headers={"HX-Request": "true"})
    assert b"Watching" in first.content
    assert Watch.objects.filter(user=user, auction=auction).exists()

    auth_client.post(url, headers={"HX-Request": "true"})
    assert not Watch.objects.exists()


def test_watchlist_and_my_listings_pages(auth_client, user):
    watched = AuctionFactory(title="Watched thing")
    Watch.objects.create(user=user, auction=watched)
    AuctionFactory(seller=user, title="My thing")

    assert b"Watched thing" in auth_client.get(reverse("auctions:watchlist")).content
    assert b"My thing" in auth_client.get(reverse("auctions:mine")).content


def test_home_lists_ending_soon(client):
    AuctionFactory(title="Ending soon item")

    response = client.get(reverse("home"))

    assert b"Ending soon item" in response.content
