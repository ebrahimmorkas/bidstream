from django.contrib import admin

from .models import Bid


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ["auction", "bidder", "amount", "created_at"]
    search_fields = ["auction__title", "bidder__email", "bidder__display_name"]
    list_select_related = ["auction", "bidder"]
    date_hierarchy = "created_at"

    def has_change_permission(self, request, obj=None) -> bool:
        return False  # bids are an immutable audit trail
