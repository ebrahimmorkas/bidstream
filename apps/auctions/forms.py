from datetime import timedelta

from django import forms
from django.conf import settings
from django.utils import timezone

from .models import Auction, Category

MAX_IMAGE_BYTES = 5 * 1024 * 1024


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%dT%H:%M", **kwargs)


class AuctionForm(forms.ModelForm):
    class Meta:
        model = Auction
        fields = [
            "title",
            "category",
            "description",
            "image",
            "starting_price",
            "min_increment",
            "reserve_price",
            "starts_at",
            "ends_at",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "starts_at": DateTimeLocalInput(),
            "ends_at": DateTimeLocalInput(),
        }
        help_texts = {"starts_at": "Times are in UTC.", "ends_at": "Times are in UTC."}

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and getattr(image, "size", 0) > MAX_IMAGE_BYTES:
            raise forms.ValidationError("Images must be 5 MB or smaller.")
        return image

    def clean(self):
        cleaned = super().clean()
        starts_at, ends_at = cleaned.get("starts_at"), cleaned.get("ends_at")
        starting, reserve = cleaned.get("starting_price"), cleaned.get("reserve_price")

        if starts_at and ends_at:
            duration = ends_at - starts_at
            min_minutes = settings.BIDSTREAM_MIN_AUCTION_MINUTES
            max_days = settings.BIDSTREAM_MAX_AUCTION_DAYS
            if duration < timedelta(minutes=min_minutes):
                self.add_error("ends_at", f"Auctions must run for at least {min_minutes} minutes.")
            elif duration > timedelta(days=max_days):
                self.add_error("ends_at", f"Auctions can run for at most {max_days} days.")
            if self.instance._state.adding and starts_at < timezone.now() - timedelta(minutes=5):
                self.add_error("starts_at", "The start time cannot be in the past.")

        if starting is not None and reserve is not None and reserve < starting:
            self.add_error("reserve_price", "Must be at least the starting price.")
        return cleaned


class AuctionFilterForm(forms.Form):
    SORTS = [
        ("ending", "Ending soonest"),
        ("newest", "Newly listed"),
        ("price_asc", "Price: low to high"),
        ("price_desc", "Price: high to low"),
        ("popular", "Most bids"),
    ]
    PHASES = [("live", "Live now"), ("upcoming", "Upcoming"), ("ended", "Ended")]

    q = forms.CharField(required=False, widget=forms.SearchInput(attrs={"placeholder": "Search"}))
    category = forms.ModelChoiceField(
        Category.objects.all(), required=False, to_field_name="slug", empty_label="All categories"
    )
    phase = forms.ChoiceField(choices=PHASES, required=False, initial="live")
    sort = forms.ChoiceField(choices=SORTS, required=False, initial="ending")
