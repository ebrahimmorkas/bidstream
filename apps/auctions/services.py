"""Auction closing.

Auctions are closed by a periodic Celery task. As a safety net (e.g. when no beat
scheduler is running in development) an expired auction is also closed lazily the
first time its page is viewed. Both paths go through :func:`close_auction`, which
locks the row, so an auction is only ever closed once.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from .models import Auction
from .signals import auction_closed

logger = logging.getLogger(__name__)


@transaction.atomic
def close_auction(auction_id: int) -> Auction | None:
    """Close an expired auction. Returns the auction if this call closed it."""
    auction = Auction.objects.select_for_update().filter(pk=auction_id).first()
    if auction is None or auction.status != Auction.Status.OPEN:
        return None
    if auction.ends_at > timezone.now():
        return None  # extended by a late bid since it was selected

    auction.status = Auction.Status.CLOSED
    auction.closed_at = timezone.now()
    auction.winner_id = auction.leading_bidder_id if auction.reserve_met else None
    auction.save(update_fields=["status", "closed_at", "winner", "updated_at"])
    logger.info("Closed auction %s (winner=%s)", auction.pk, auction.winner_id)

    transaction.on_commit(lambda: auction_closed.send(sender=Auction, auction=auction))
    return auction


def close_due_auctions() -> int:
    closed = 0
    for auction_id in Auction.objects.due_for_closing().values_list("pk", flat=True):
        if close_auction(auction_id):
            closed += 1
    return closed
