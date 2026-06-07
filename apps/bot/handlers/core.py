from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to *Football Intel*\n\n"
        "Your personal football assistant\n\n"
        "Get started:\n"
        "Follow a team: /follow arsenal\n"
        "Live scores: /live\n"
        "Today matches: /scores\n\n"
        "Type /help for all commands",
        parse_mode=ParseMode.MARKDOWN,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚽ *Football Intel Commands*\n\n"
        "*Matches*\n"
        "/live — All live matches\n"
        "/scores — Today's results\n"
        "/fixtures team — Upcoming fixtures\n"
        "/standings comp — League table\n"
        "/match id — Match detail\n\n"
        "*Personalisation*\n"
        "/follow team — Follow a team\n"
        "/unfollow team — Unfollow\n"
        "/following — Your teams\n"
        "/alerts on or off — Toggle alerts\n"
        "/me — Your profile\n\n"
        "*Bookmarks*\n"
        "/bookmark id — Save article\n"
        "/bookmarks — Saved articles\n"
        "/unbookmark id — Remove",
        parse_mode=ParseMode.MARKDOWN,
    )


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Unknown command. Type /help to see all commands."
    )