from rest_framework import serializers

from apps.auctions.models import Auction
from apps.bidding.models import Bid


class AuctionSerializer(serializers.ModelSerializer):
    seller = serializers.CharField(source="seller.display_name", read_only=True)
    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    phase = serializers.CharField(read_only=True)
    price = serializers.DecimalField(
        source="display_price", max_digits=12, decimal_places=2, read_only=True
    )
    minimum_next_bid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    reserve_met = serializers.BooleanField(read_only=True)
    url = serializers.HyperlinkedIdentityField(view_name="api:auction-detail")

    class Meta:
        model = Auction
        fields = [
            "id",
            "url",
            "title",
            "description",
            "category",
            "seller",
            "image",
            "phase",
            "status",
            "starting_price",
            "price",
            "minimum_next_bid",
            "min_increment",
            "bid_count",
            "reserve_met",
            "starts_at",
            "ends_at",
        ]


class BidSerializer(serializers.ModelSerializer):
    bidder = serializers.CharField(source="bidder.masked_name", read_only=True)

    class Meta:
        model = Bid
        fields = ["id", "bidder", "amount", "created_at"]
        read_only_fields = ["id", "bidder", "created_at"]


class PlaceBidSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
