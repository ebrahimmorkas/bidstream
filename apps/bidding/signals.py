"""Domain events emitted by the bidding service.

They are sent from ``transaction.on_commit`` so receivers (WebSocket broadcast,
outbid emails, ...) only ever see bids that were actually persisted.
"""

from django.dispatch import Signal

# kwargs: bid, auction, previous_leader_id, extended
bid_placed = Signal()
