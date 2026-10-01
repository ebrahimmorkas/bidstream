from django.conf import settings
from django.db import models

from apps.auctions.models import MONEY, Auction


class Bid(models.Model):
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name="bids")
    bidder = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bids"
    )
    amount = models.DecimalField(**MONEY)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-amount", "created_at"]
        indexes = [models.Index(fields=["auction", "-amount"])]
        constraints = [
            # Bids on an auction strictly increase, so amounts are unique per auction.
            models.UniqueConstraint(fields=["auction", "amount"], name="unique_bid_amount"),
        ]

    def __str__(self) -> str:
        return f"{self.bidder} bid {self.amount} on {self.auction}"
