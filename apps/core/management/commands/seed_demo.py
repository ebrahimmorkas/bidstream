from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.auctions.models import Auction, Category
from apps.bidding.services import place_bid

DEMO_PASSWORD = "demo-pass-123"

CATEGORIES = ["Cameras", "Watches", "Art", "Music", "Collectibles"]

# title, category, starting price, increment, reserve, ends in (minutes), bids
AUCTIONS = [
    ("Leica M6 film camera", "Cameras", "900", "25", "1400", 4, ["950", "1000", "1100"]),
    ("Omega Speedmaster 1969", "Watches", "3000", "100", None, 90, ["3100", "3300"]),
    ("Signed Beatles LP", "Music", "250", "10", None, 60 * 24, ["260"]),
    ("Abstract oil on canvas", "Art", "400", "20", "800", 60 * 6, []),
    ("1st edition Pokemon Charizard", "Collectibles", "1500", "50", None, 30, ["1550", "1700"]),
    ("Fender Stratocaster 1978", "Music", "1800", "50", None, 60 * 48, []),
]


class Command(BaseCommand):
    help = "Create demo users, categories and auctions with bidding activity."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        seller = self._user(User, "seller@bidstream.dev", "VintageVault")
        bidders = [
            self._user(User, f"{name.lower()}@bidstream.dev", name)
            for name in ["Alice", "Bobby", "Carla"]
        ]

        categories = {
            name: Category.objects.get_or_create(slug=name.lower(), defaults={"name": name})[0]
            for name in CATEGORIES
        }

        now = timezone.now()
        created = 0
        for title, category, start, step, reserve, minutes, bids in AUCTIONS:
            if Auction.objects.filter(title=title).exists():
                continue
            auction = Auction.objects.create(
                seller=seller,
                category=categories[category],
                title=title,
                description=f"{title}. Authenticated and in excellent condition.",
                starting_price=Decimal(start),
                min_increment=Decimal(step),
                reserve_price=Decimal(reserve) if reserve else None,
                starts_at=now - timedelta(hours=1),
                ends_at=now + timedelta(minutes=minutes),
            )
            for i, amount in enumerate(bids):
                place_bid(
                    auction_id=auction.pk, bidder=bidders[i % len(bidders)], amount=Decimal(amount)
                )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created} auction(s).\n"
                f"  seller: seller@bidstream.dev / {DEMO_PASSWORD}\n"
                f"  bidders: alice@, bobby@, carla@bidstream.dev / {DEMO_PASSWORD}"
            )
        )

    @staticmethod
    def _user(User, email, display_name):
        user, _ = User.objects.get_or_create(email=email, defaults={"display_name": display_name})
        user.set_password(DEMO_PASSWORD)
        user.save()
        return user
