from django.core.management.base import BaseCommand

from apps.auctions.services import close_due_auctions


class Command(BaseCommand):
    help = "Close every auction whose end time has passed (cron alternative to Celery beat)."

    def handle(self, *args, **options):
        count = close_due_auctions()
        self.stdout.write(self.style.SUCCESS(f"Closed {count} auction(s)."))
