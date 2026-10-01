"""Channel-layer group names, kept in one place so producers and consumers agree."""

FEED_GROUP = "auctions.feed"


def auction_group(auction_id: int) -> str:
    return f"auction.{auction_id}"
