from telegram import Update
from telegram.ext import ContextTypes
from asgiref.sync import sync_to_async


async def bookmark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bookmark feature coming soon when news is built.")


async def bookmarks_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bookmarks feature coming soon.")


async def unbookmark(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Unbookmark feature coming soon.")