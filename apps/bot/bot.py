import logging
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from django.conf import settings

logger = logging.getLogger(__name__)


def build_application() -> Application:
    app = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .build()
    )

    # Import handlers here to avoid circular imports
    from apps.bot.handlers.core import start, help_command, unknown_command
    from apps.bot.handlers.matches import live, scores, fixtures, standings, match_detail
    from apps.bot.handlers.user import follow, unfollow, following, alerts, me
    from apps.bot.handlers.bookmarks import bookmark, bookmarks_list, unbookmark

    # Core
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    # Matches
    app.add_handler(CommandHandler("live", live))
    app.add_handler(CommandHandler("scores", scores))
    app.add_handler(CommandHandler("fixtures", fixtures))
    app.add_handler(CommandHandler("standings", standings))
    app.add_handler(CommandHandler("match", match_detail))

    # Personalisation
    app.add_handler(CommandHandler("follow", follow))
    app.add_handler(CommandHandler("unfollow", unfollow))
    app.add_handler(CommandHandler("following", following))
    app.add_handler(CommandHandler("alerts", alerts))
    app.add_handler(CommandHandler("me", me))

    # Bookmarks
    app.add_handler(CommandHandler("bookmark", bookmark))
    app.add_handler(CommandHandler("bookmarks", bookmarks_list))
    app.add_handler(CommandHandler("unbookmark", unbookmark))

    # Inline keyboard callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Catch-all unknown commands
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger.info("Bot built successfully")
    return app


async def handle_callback(update, context):
    query = update.callback_query
    await query.answer()
    action, _, payload = query.data.partition(":")
    context.args = [payload]

    from apps.bot.handlers.matches import live
    handlers_map = {
        "live": live,
    }
    handler = handlers_map.get(action)
    if handler:
        await handler(update, context)
    else:
        await query.edit_message_text("❓ Unknown action.")