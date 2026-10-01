from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone

from apps.core.models import TimeStampedModel

MONEY = {"max_digits": 12, "decimal_places": 2}


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name


class AuctionQuerySet(models.QuerySet):
    def live(self, now=None):
        now = now or timezone.now()
        return self.filter(status=Auction.Status.OPEN, starts_at__lte=now, ends_at__gt=now)

    def upcoming(self, now=None):
        return self.filter(status=Auction.Status.OPEN, starts_at__gt=now or timezone.now())

    def finished(self):
        return self.filter(status=Auction.Status.CLOSED)

    def due_for_closing(self, now=None):
        return self.filter(status=Auction.Status.OPEN, ends_at__lte=now or timezone.now())


class Auction(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        CANCELLED = "cancelled", "Cancelled"

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="auctions"
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="auctions"
    )
    title = models.CharField(max_length=120)
    description = models.TextField()
    image = models.ImageField(upload_to="auctions/%Y/%m/", blank=True)

    starting_price = models.DecimalField(**MONEY, validators=[MinValueValidator(Decimal("0.01"))])
    min_increment = models.DecimalField(
        **MONEY, default=Decimal("1.00"), validators=[MinValueValidator(Decimal("0.01"))]
    )
    reserve_price = models.DecimalField(
        **MONEY,
        null=True,
        blank=True,
        help_text="Hidden minimum price. The item is not sold if bidding stays below it.",
    )
    current_price = models.DecimalField(**MONEY, null=True, blank=True, editable=False)
    bid_count = models.PositiveIntegerField(default=0, editable=False)
    leading_bidder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="leading_auctions",
    )

    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="won_auctions",
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    watchers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="Watch", related_name="watchlist", blank=True
    )

    objects = AuctionQuerySet.as_manager()

    class Meta:
        ordering = ["ends_at"]
        indexes = [
            models.Index(fields=["status", "ends_at"]),
            models.Index(fields=["status", "starts_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")), name="auction_ends_after_start"
            ),
            models.CheckConstraint(
                condition=Q(reserve_price__isnull=True) | Q(reserve_price__gte=F("starting_price")),
                name="auction_reserve_not_below_start",
            ),
        ]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("auctions:detail", args=[self.pk])

    # --- derived state -------------------------------------------------------
    @property
    def phase(self) -> str:
        """Human-facing lifecycle phase: upcoming, live, ending, closed or cancelled."""
        if self.status != self.Status.OPEN:
            return self.status
        now = timezone.now()
        if now < self.starts_at:
            return "upcoming"
        if now < self.ends_at:
            return "live"
        return "ending"  # past end time, waiting for the closing job

    @property
    def is_live(self) -> bool:
        return self.phase == "live"

    @property
    def display_price(self) -> Decimal:
        return self.current_price if self.current_price is not None else self.starting_price

    @property
    def minimum_next_bid(self) -> Decimal:
        if self.current_price is None:
            return self.starting_price
        return self.current_price + self.min_increment

    @property
    def reserve_met(self) -> bool:
        if self.reserve_price is None:
            return True
        return self.current_price is not None and self.current_price >= self.reserve_price

    def recent_bids(self, limit: int = 10):
        return self.bids.select_related("bidder")[:limit]

    @property
    def is_editable(self) -> bool:
        return self.status == self.Status.OPEN and self.bid_count == 0


class Watch(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "auction"], name="unique_watch"),
        ]

    def __str__(self) -> str:
        return f"{self.user} watches {self.auction}"
