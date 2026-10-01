import logging
from smtplib import SMTPException

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string

from apps.auctions.models import Auction

logger = logging.getLogger(__name__)

RETRY = {
    "autoretry_for": (SMTPException, ConnectionError),
    "retry_backoff": True,
    "retry_kwargs": {"max_retries": 5},
}


def _send(template: str, subject: str, recipient: str, context: dict) -> None:
    body = render_to_string(f"notifications/{template}.txt", context)
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient])


def _site_url(auction: Auction) -> str:
    return f"{settings.SITE_URL.rstrip('/')}{auction.get_absolute_url()}"


@shared_task(**RETRY)
def send_outbid_notice(auction_id: int, user_id: int) -> None:
    auction = Auction.objects.filter(pk=auction_id).first()
    user = get_user_model().objects.filter(pk=user_id).first()
    if auction is None or user is None:
        return
    _send(
        "outbid",
        f"You've been outbid on {auction.title}",
        user.email,
        {"user": user, "auction": auction, "url": _site_url(auction)},
    )


@shared_task(**RETRY)
def send_auction_results(auction_id: int) -> None:
    auction = Auction.objects.select_related("seller", "winner").filter(pk=auction_id).first()
    if auction is None:
        return
    context = {"auction": auction, "url": _site_url(auction)}

    _send(
        "seller_result", f"Your auction has ended: {auction.title}", auction.seller.email, context
    )
    if auction.winner:
        _send("winner", f"You won {auction.title}!", auction.winner.email, context)
