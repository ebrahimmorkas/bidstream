import django_filters
from django.db.models import F
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.auctions.models import Auction
from apps.bidding.services import BidRejected, place_bid

from .serializers import AuctionSerializer, BidSerializer, PlaceBidSerializer


class AuctionFilter(django_filters.FilterSet):
    phase = django_filters.ChoiceFilter(
        choices=[("live", "Live"), ("upcoming", "Upcoming"), ("ended", "Ended")],
        method="filter_phase",
    )
    category = django_filters.CharFilter(field_name="category__slug")
    min_price = django_filters.NumberFilter(field_name="effective_price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="effective_price", lookup_expr="lte")

    class Meta:
        model = Auction
        fields = ["phase", "category"]

    def filter_phase(self, queryset, name, value):
        return {
            "live": queryset.live,
            "upcoming": queryset.upcoming,
            "ended": queryset.finished,
        }[value]()


class AuctionViewSet(viewsets.ReadOnlyModelViewSet):
    """Browse auctions. Writes happen through the bids sub-resource."""

    serializer_class = AuctionSerializer
    permission_classes = [permissions.AllowAny]
    filterset_class = AuctionFilter
    search_fields = ["title", "description"]
    ordering_fields = ["ends_at", "created_at", "effective_price", "bid_count"]
    ordering = ["ends_at"]

    def get_queryset(self):
        return (
            Auction.objects.exclude(status=Auction.Status.CANCELLED)
            .annotate(effective_price=Coalesce(F("current_price"), F("starting_price")))
            .select_related("seller", "category")
        )

    def get_throttles(self):
        if self.action == "bids" and self.request.method == "POST":
            self.throttle_scope = "bids"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    @extend_schema(
        methods=["POST"],
        request=PlaceBidSerializer,
        responses={
            201: BidSerializer,
            401: OpenApiResponse(description="Authentication required"),
            409: OpenApiResponse(description="Bid rejected by auction rules"),
        },
    )
    @extend_schema(methods=["GET"], responses=BidSerializer(many=True))
    @action(detail=True, methods=["get", "post"], permission_classes=[permissions.AllowAny])
    def bids(self, request, pk=None):
        auction = get_object_or_404(Auction, pk=pk)

        if request.method == "GET":
            page = self.paginate_queryset(auction.bids.select_related("bidder"))
            return self.get_paginated_response(BidSerializer(page, many=True).data)

        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        payload = PlaceBidSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            result = place_bid(
                auction_id=auction.pk, bidder=request.user, amount=payload.validated_data["amount"]
            )
        except BidRejected as exc:
            return Response(
                {"detail": str(exc), "code": "bid_rejected"}, status=status.HTTP_409_CONFLICT
            )
        data = BidSerializer(result.bid).data
        data["auction_extended"] = result.extended
        return Response(data, status=status.HTTP_201_CREATED)
