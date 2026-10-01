from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from apps.auctions.models import Auction

from .services import BidRejected, parse_amount, place_bid


@login_required
@require_POST
def place_bid_view(request, pk: int):
    auction = get_object_or_404(Auction, pk=pk)
    error, success = None, None
    try:
        result = place_bid(
            auction_id=auction.pk, bidder=request.user, amount=parse_amount(request.POST["amount"])
        )
    except (BidRejected, KeyError) as exc:
        error = str(exc) if isinstance(exc, BidRejected) else "Enter a valid amount."
    else:
        auction = result.auction
        success = f"You are the highest bidder at ${result.bid.amount:,.2f}."
        if result.extended:
            success += " The auction was extended to give others a chance to respond."

    if request.headers.get("HX-Request"):
        auction.refresh_from_db()
        context = {"auction": auction, "bid_error": error, "bid_success": success}
        # HTMX does not swap 4xx responses by default, so errors are rendered with 200.
        return render(request, "bidding/_bid_panel.html", context)

    if error:
        messages.error(request, error)
    else:
        messages.success(request, success)
    return redirect(auction)


class MyBidsView(LoginRequiredMixin, ListView):
    template_name = "bidding/my_bids.html"
    context_object_name = "auctions"
    paginate_by = 20

    def get_queryset(self):
        return (
            Auction.objects.filter(bids__bidder=self.request.user)
            .annotate(my_max_bid=Max("bids__amount"))
            .select_related("leading_bidder", "winner")
            .order_by("-ends_at")
        )
