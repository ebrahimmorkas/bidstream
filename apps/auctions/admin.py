from django.contrib import admin

from .models import Auction, Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "seller",
        "status",
        "starting_price",
        "current_price",
        "bid_count",
        "ends_at",
    ]
    list_filter = ["status", "category"]
    search_fields = ["title", "seller__email", "seller__display_name"]
    date_hierarchy = "ends_at"
    readonly_fields = ["current_price", "bid_count", "winner", "closed_at"]
    list_select_related = ["seller"]
