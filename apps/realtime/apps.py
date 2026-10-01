from django.apps import AppConfig


class RealtimeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.realtime"

    def ready(self) -> None:
        from apps.bidding.signals import bid_placed

        from .broadcast import on_bid_placed

        bid_placed.connect(on_bid_placed, dispatch_uid="realtime.broadcast_bid")
