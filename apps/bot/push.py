import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    queue="critical",
    name="apps.bot.push.send_match_event_alert",
)
def send_match_event_alert(match_event_id: int):
    """
    Called by the score poller when a new match event is detected.
    Finds all followers of either team and sends the alert.
    """
    from apps.matches.models import MatchEvent
    from apps.bot.models import TelegramUser

    try:
        event = MatchEvent.objects.select_related(
            "match__home_team",
            "match__away_team",
            "match__competition",
            "team",
        ).get(pk=match_event_id)
    except MatchEvent.DoesNotExist:
        logger.error("MatchEvent %d not found", match_event_id)
        return

    message = event.format_alert()

    # Find users following either team in this match
    home_team_api_id = event.match.home_team.api_id
    away_team_api_id = event.match.away_team.api_id

    # Determine alert type to check user preferences
    alert_field_map = {
        "GOAL": "alert_goals",
        "OWN_GOAL": "alert_goals",
        "PENALTY": "alert_goals",
        "YELLOW": "alert_cards",
        "RED": "alert_cards",
        "YELLOW_RED": "alert_cards",
        "SUB": "alert_goals",  # subs go to all goal-alert users
        "VAR": "alert_goals",
        "HT": "alert_goals",
        "FT": "alert_goals",
    }
    alert_field = alert_field_map.get(event.event_type, "alert_goals")

    users = TelegramUser.objects.filter(
        followed_clubs__api_id__in=[home_team_api_id, away_team_api_id],
        **{alert_field: True},
    ).distinct().values_list("telegram_id", flat=True)

    sent = 0
    for telegram_id in users:
        success = _send_message(telegram_id, message)
        if success:
            sent += 1

    logger.info(
        "Alert sent for event %d (%s) to %d users",
        match_event_id, event.event_type, sent,
    )