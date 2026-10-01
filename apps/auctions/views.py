from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import F, Q
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .forms import AuctionFilterForm, AuctionForm
from .models import Auction, Watch

SORT_ORDER = {
    "ending": ["ends_at"],
    "newest": ["-created_at"],
    "price_asc": ["effective_price"],
    "price_desc": ["-effective_price"],
    "popular": ["-bid_count", "ends_at"],
}


class AuctionListView(ListView):
    template_name = "auctions/list.html"
    context_object_name = "auctions"
    paginate_by = 12

    def get_template_names(self):
        # HTMX filter requests only need the results fragment.
        if self.request.headers.get("HX-Request"):
            return ["auctions/_results.html"]
        return [self.template_name]

    def get_queryset(self):
        self.filters = AuctionFilterForm(self.request.GET or None)
        data = self.filters.cleaned_data if self.filters.is_valid() else {}
        phase = data.get("phase") or "live"

        qs = {
            "live": Auction.objects.live(),
            "upcoming": Auction.objects.upcoming(),
            "ended": Auction.objects.finished(),
        }[phase]
        if query := data.get("q"):
            qs = qs.filter(Q(title__icontains=query) | Q(description__icontains=query))
        if category := data.get("category"):
            qs = qs.filter(category=category)

        order = SORT_ORDER.get(data.get("sort") or "ending", SORT_ORDER["ending"])
        if phase == "ended" and not data.get("sort"):
            order = ["-ends_at"]
        return (
            qs.annotate(effective_price=Coalesce(F("current_price"), F("starting_price")))
            .select_related("category", "seller")
            .order_by(*order)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filters"] = self.filters
        query = self.request.GET.copy()
        query.pop("page", None)
        context["querystring"] = query.urlencode()
        return context


class AuctionDetailView(DetailView):
    model = Auction
    template_name = "auctions/detail.html"
    context_object_name = "auction"

    def get_queryset(self):
        return Auction.objects.select_related("seller", "category", "winner")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["is_watching"] = (
            user.is_authenticated and Watch.objects.filter(user=user, auction=self.object).exists()
        )
        return context


class AuctionCreateView(LoginRequiredMixin, CreateView):
    model = Auction
    form_class = AuctionForm
    template_name = "auctions/form.html"

    def form_valid(self, form):
        form.instance.seller = self.request.user
        messages.success(self.request, "Your auction has been listed.")
        return super().form_valid(form)


class SellerOnlyMixin(LoginRequiredMixin, UserPassesTestMixin):
    def get_queryset(self):
        return Auction.objects.filter(seller=self.request.user)

    def test_func(self):
        auction = self.get_object()
        if not auction.is_editable:
            raise PermissionDenied("Auctions cannot be changed once bidding has started.")
        return True


class AuctionUpdateView(SellerOnlyMixin, UpdateView):
    model = Auction
    form_class = AuctionForm
    template_name = "auctions/form.html"

    def form_valid(self, form):
        messages.success(self.request, "Auction updated.")
        return super().form_valid(form)


class AuctionCancelView(SellerOnlyMixin, View):
    def post(self, request, pk):
        auction = get_object_or_404(self.get_queryset(), pk=pk)
        auction.status = Auction.Status.CANCELLED
        auction.save(update_fields=["status", "updated_at"])
        messages.info(request, f"'{auction.title}' was cancelled.")
        return redirect("auctions:mine")

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])


class MyListingsView(LoginRequiredMixin, ListView):
    template_name = "auctions/my_listings.html"
    context_object_name = "auctions"
    paginate_by = 20

    def get_queryset(self):
        return Auction.objects.filter(seller=self.request.user).order_by("-created_at")


class WatchlistView(LoginRequiredMixin, ListView):
    template_name = "auctions/watchlist.html"
    context_object_name = "auctions"

    def get_queryset(self):
        return self.request.user.watchlist.select_related("category").order_by("ends_at")


class ToggleWatchView(LoginRequiredMixin, View):
    """Add/remove an auction from the watchlist; returns the button fragment for HTMX."""

    def post(self, request, pk):
        auction = get_object_or_404(Auction, pk=pk)
        watch, created = Watch.objects.get_or_create(user=request.user, auction=auction)
        if not created:
            watch.delete()
        context = {"auction": auction, "is_watching": created}
        if request.headers.get("HX-Request"):
            return render(request, "auctions/_watch_button.html", context)
        return redirect(auction)
