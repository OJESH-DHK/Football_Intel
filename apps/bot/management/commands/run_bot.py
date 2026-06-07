import logging
from django.core.management.base import BaseCommand
from apps.bot.bot import build_application

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Start the Telegram bot in polling mode"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting bot in POLLING mode..."))
        app = build_application()
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )
