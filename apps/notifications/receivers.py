from django.dispatch import receiver

from apps.auctions.signals import auction_closed
from apps.bidding.signals import bid_placed

from .tasks import send_auction_results, send_outbid_notice


@receiver(bid_placed, dispatch_uid="notifications.outbid")
def notify_outbid(sender, bid, auction, previous_leader_id, **kwargs) -> None:
    if previous_leader_id and previous_leader_id != bid.bidder_id:
        send_outbid_notice.delay(auction.pk, previous_leader_id)


@receiver(auction_closed, dispatch_uid="notifications.results")
def notify_results(sender, auction, **kwargs) -> None:
    send_auction_results.delay(auction.pk)
