"""Domain events emitted by the auctions app (sent after the transaction commits)."""

from django.dispatch import Signal

# kwargs: auction
auction_closed = Signal()
