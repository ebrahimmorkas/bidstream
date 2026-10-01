from celery import shared_task

from .services import close_due_auctions


@shared_task
def close_expired_auctions() -> int:
    return close_due_auctions()
