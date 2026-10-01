from datetime import timedelta
from decimal import Decimal

import factory
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.auctions.models import Auction, Category


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category
        django_get_or_create = ["slug"]

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.Sequence(lambda n: f"category-{n}")


class AuctionFactory(factory.django.DjangoModelFactory):
    """A live auction by default (started an hour ago, ends tomorrow)."""

    class Meta:
        model = Auction

    seller = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f"Vintage item {n}")
    description = "A lovely item in great condition."
    starting_price = Decimal("10.00")
    min_increment = Decimal("1.00")
    starts_at = factory.LazyFunction(lambda: timezone.now() - timedelta(hours=1))
    ends_at = factory.LazyFunction(lambda: timezone.now() + timedelta(days=1))

    class Params:
        upcoming = factory.Trait(
            starts_at=factory.LazyFunction(lambda: timezone.now() + timedelta(hours=2)),
            ends_at=factory.LazyFunction(lambda: timezone.now() + timedelta(days=2)),
        )
        expired = factory.Trait(
            starts_at=factory.LazyFunction(lambda: timezone.now() - timedelta(days=2)),
            ends_at=factory.LazyFunction(lambda: timezone.now() - timedelta(minutes=1)),
        )
