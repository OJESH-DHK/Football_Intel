from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from asgiref.sync import sync_to_async

STATUS_EMOJI = {
    "1H": "🟢", "2H": "🟢", "HT": "🔔",
    "FT": "🏁", "NS": "🕐", "PST": "⚠️",
}


def fmt(match):
    emoji = STATUS_EMOJI.get(match.status, "⚽")
    h = match.home_team.short_name or match.home_team.name
    a = match.away_team.short_name or match.away_team.name
    if match.status in ("1H", "2H", "HT", "FT"):
        return f"{emoji} {h} {match.home_score}-{match.away_score} {a}"
    return f"{emoji} {h} vs {a} — {match.kickoff.strftime('%H:%M')}"


async def live(update: Update, context: ContextTypes.DEFAULT_TYPE):
    club = " ".join(context.args).strip() if context.args else None

    def _query():
        from apps.matches.models import Match
        qs = Match.objects.filter(
            status__in=["1H", "2H", "HT"]
        ).select_related("home_team", "away_team", "competition")
        if club:
            qs = qs.filter(
                home_team__name__icontains=club
            ) | Match.objects.filter(
                away_team__name__icontains=club,
                status__in=["1H", "2H", "HT"]
            ).select_related("home_team", "away_team", "competition")
        return list(qs.order_by("kickoff"))

    matches = await sync_to_async(_query)()

    if not matches:
        await update.message.reply_text("No live matches right now\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    lines = ["🟢 *Live Matches*\n"] + [fmt(m) for m in matches]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)


async def scores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    def _query():
        from apps.matches.models import Match
        from django.utils import timezone
        today = timezone.now().date()
        return list(
            Match.objects.filter(kickoff__date=today)
            .select_related("home_team", "away_team", "competition")
            .order_by("kickoff")
        )

    matches = await sync_to_async(_query)()

    if not matches:
        await update.message.reply_text("No matches today\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    lines = ["📊 *Today's Matches*\n"] + [fmt(m) for m in matches]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)


async def fixtures(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /fixtures arsenal", parse_mode=ParseMode.MARKDOWN_V2)
        return

    club = " ".join(context.args).strip()

    def _query():
        from apps.matches.models import Match
        from django.utils import timezone
        now = timezone.now()
        home = Match.objects.filter(
            home_team__name__icontains=club, status="NS", kickoff__gte=now
        )
        away = Match.objects.filter(
            away_team__name__icontains=club, status="NS", kickoff__gte=now
        )
        return list(
            (home | away).select_related(
                "home_team", "away_team", "competition"
            ).order_by("kickoff")[:5]
        )

    matches = await sync_to_async(_query)()

    if not matches:
        await update.message.reply_text(f"No fixtures found for {club}\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    lines = [f"📅 *Fixtures — {club}*\n"] + [fmt(m) for m in matches]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN_V2)


async def standings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: /standings pl\nOptions: pl, cl, laliga, bundesliga, seriea, ligue1",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    code = context.args[0].lower()

    def _query():
        from django.core.cache import cache
        return cache.get(f"standings:{code}")

    data = await sync_to_async(_query)()

    if not data:
        await update.message.reply_text(
            f"Standings for `{code}` not loaded yet\. Try again in a few minutes\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    await update.message.reply_text(data, parse_mode=ParseMode.MARKDOWN_V2)


async def match_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /match 12345", parse_mode=ParseMode.MARKDOWN_V2)
        return

    try:
        match_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Match ID must be a number\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    def _query():
        from apps.matches.models import Match
        try:
            m = Match.objects.select_related(
                "home_team", "away_team", "competition"
            ).get(pk=match_id)
            events = list(m.events.select_related("team").order_by("minute"))
            return m, events
        except Match.DoesNotExist:
            return None, []

    match, events = await sync_to_async(_query)()

    if not match:
        await update.message.reply_text(f"Match {match_id} not found\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    lines = [
        f"⚽ *{match.home_team.name} {match.home_score or 0}\-{match.away_score or 0} {match.away_team.name}*",
        f"_{match.competition.name} — {match.status}_\n",
    ]

    for e in events:
        emoji = {"GOAL": "⚽", "YELLOW": "🟨", "RED": "🟥", "SUB": "🔄", "HT": "🔔", "FT": "🏁"}.get(e.event_type, "•")
        lines.append(f"{emoji} {e.minute}' {e.player_name}")

    if not events:
        lines.append("_No events yet_")

    await update.message