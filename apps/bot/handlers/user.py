from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from asgiref.sync import sync_to_async


async def _get_or_create_user(telegram_user):
    def _db():
        from apps.bot.models import TelegramUser
        user, _ = TelegramUser.objects.get_or_create(
            telegram_id=telegram_user.id,
            defaults={
                "username": telegram_user.username or "",
                "first_name": telegram_user.first_name or "",
            },
        )
        return user
    return await sync_to_async(_db)()


async def follow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /follow arsenal")
        return
    team_name = " ".join(context.args).strip()
    user = await _get_or_create_user(update.effective_user)

    def _db():
        from apps.matches.models import Team
        team = Team.objects.filter(name__icontains=team_name).first()
        if not team:
            return None
        if user.followed_teams.filter(pk=team.pk).exists():
            return f"You already follow *{team.name}*"
        user.followed_teams.add(team)
        return f"Now following *{team.name}*"

    result = await sync_to_async(_db)()
    if result is None:
        await update.message.reply_text(f"Team '{team_name}' not found.")
    else:
        await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)


async def unfollow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /unfollow arsenal")
        return
    team_name = " ".join(context.args).strip()
    user = await _get_or_create_user(update.effective_user)

    def _db():
        team = user.followed_teams.filter(name__icontains=team_name).first()
        if not team:
            return f"You don't follow any team matching '{team_name}'"
        user.followed_teams.remove(team)
        return f"Unfollowed *{team.name}*"

    result = await sync_to_async(_db)()
    await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)


async def following(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_or_create_user(update.effective_user)
    teams = await sync_to_async(lambda: list(user.followed_teams.all()))()
    if not teams:
        await update.message.reply_text(
            "You don't follow any teams yet.\n\nTry: /follow arsenal"
        )
        return
    lines = "\n".join(f"• {t.name}" for t in teams)
    await update.message.reply_text(
        f"⭐ *Your teams ({len(teams)}):*\n\n{lines}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_or_create_user(update.effective_user)
    if not context.args:
        await update.message.reply_text(
            f"🔔 *Alert Settings*\n\n"
            f"Goals: {'✅' if user.alert_goals else '❌'}\n"
            f"Cards: {'✅' if user.alert_cards else '❌'}\n\n"
            f"Toggle: /alerts on or /alerts off",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    arg = context.args[0].lower()

    def _db():
        if arg == "on":
            user.alert_goals = True
            user.alert_cards = True
            user.save(update_fields=["alert_goals", "alert_cards"])
            return "All alerts enabled"
        elif arg == "off":
            user.alert_goals = False
            user.alert_cards = False
            user.save(update_fields=["alert_goals", "alert_cards"])
            return "All alerts disabled"
        elif arg == "goals":
            user.alert_goals = not user.alert_goals
            user.save(update_fields=["alert_goals"])
            return f"Goal alerts {'enabled' if user.alert_goals else 'disabled'}"
        elif arg == "cards":
            user.alert_cards = not user.alert_cards
            user.save(update_fields=["alert_cards"])
            return f"Card alerts {'enabled' if user.alert_cards else 'disabled'}"
        return f"Unknown option: {arg}"

    result = await sync_to_async(_db)()
    await update.message.reply_text(result)


async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_or_create_user(update.effective_user)

    def _db():
        teams = list(user.followed_teams.all())
        bookmarks = user.bookmarks.count()
        return teams, bookmarks

    teams, bookmarks = await sync_to_async(_db)()
    team_list = ", ".join(t.name for t in teams) if teams else "None"

    await update.message.reply_text(
        f"👤 *Your Profile*\n\n"
        f"Username: @{user.username or 'N/A'}\n"
        f"Following: {team_list}\n"
        f"Bookmarks: {bookmarks}\n\n"
        f"Goals alerts: {'✅' if user.alert_goals else '❌'}\n"
        f"Card alerts: {'✅' if user.alert_cards else '❌'}",
        parse_mode=ParseMode.MARKDOWN,
    )