import pytest
from django.core.management import call_command

from apps.auctions.models import Auction
from apps.bidding.models import Bid


@pytest.mark.django_db
def test_seed_demo_is_idempotent():
    call_command("seed_demo")
    call_command("seed_demo")

    assert Auction.objects.count() == 6
    assert Bid.objects.count() == 8
    assert Auction.objects.live().count() == 6
