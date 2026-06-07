import logging
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    queue="critical",
    max_retries=3,
    name="apps.matches.tasks.poll_live_scores",
)
def poll_live_scores(self):
    """
    Runs every 60 seconds via Celery Beat.
    1. Fetches all live matches from tracked leagues
    2. Updates match scores in DB
    3. Detects new events
    4. Triggers Telegram alerts for new events
    """
    from .poller import APIFootballClient, parse_event_type
    from .models import Match, MatchEvent, Competition, Team

    client = APIFootballClient()
    fixtures = client.get_live_fixtures()

    if not fixtures:
        logger.info("No live matches in tracked leagues right now.")
        return "no_live_matches"

    logger.info("Processing %d live fixtures", len(fixtures))

    for fixture in fixtures:
        try:
            _process_fixture(fixture, client, parse_event_type)
        except Exception as e:
            logger.error("Error processing fixture %s: %s", fixture["fixture"]["id"], e)

    return f"processed_{len(fixtures)}_fixtures"


def _process_fixture(fixture: dict, client, parse_event_type):
    """Process a single fixture — update scores and detect new events."""
    from .models import Match, MatchEvent, Competition, Team

    f = fixture["fixture"]
    league = fixture["league"]
    teams = fixture["teams"]
    goals = fixture["goals"]
    score = fixture["score"]

    # ── 1. Get or create Competition ─────────────────────────────────
    competition, _ = Competition.objects.get_or_create(
        api_id=league["id"],
        defaults={
            "name": league["name"],
            "country": league["country"],
            "logo_url": league.get("logo") or "",
            "flag_url": league.get("flag") or "",
            "season": league.get("season", 2026),
        },
    )

    # ── 2. Get or create Teams ────────────────────────────────────────
    home_team, _ = Team.objects.get_or_create(
        api_id=teams["home"]["id"],
        defaults={
            "name": teams["home"]["name"],
            "logo_url": teams["home"].get("logo") or "",
        },
    )
    away_team, _ = Team.objects.get_or_create(
        api_id=teams["away"]["id"],
        defaults={
            "name": teams["away"]["name"],
            "logo_url": teams["away"].get("logo") or "",
        },
    )

    # ── 3. Get or create Match, update score + status ─────────────────
    from django.utils.dateparse import parse_datetime

    match, created = Match.objects.get_or_create(
        api_id=f["id"],
        defaults={
            "competition": competition,
            "home_team": home_team,
            "away_team": away_team,
            "kickoff": parse_datetime(f["date"]),
            "venue": f.get("venue", {}).get("name") or "",
            "city": f.get("venue", {}).get("city") or "",
            "referee": f.get("referee") or "",
            "round": league.get("round") or "",
            "status": f["status"]["short"],
            "home_score": goals.get("home"),
            "away_score": goals.get("away"),
            "home_score_ht": score["halftime"].get("home"),
            "away_score_ht": score["halftime"].get("away"),
            "minute": f["status"].get("elapsed"),
        },
    )

    if not created:
        # Update live score and status
        match.status = f["status"]["short"]
        match.home_score = goals.get("home")
        match.away_score = goals.get("away")
        match.home_score_ht = score["halftime"].get("home")
        match.away_score_ht = score["halftime"].get("away")
        match.minute = f["status"].get("elapsed")
        match.save(update_fields=[
            "status", "home_score", "away_score",
            "home_score_ht", "away_score_ht", "minute", "last_synced"
        ])

    # ── 4. Process events from inline fixture data ────────────────────
    events = fixture.get("events", [])
    for event in events:
        _process_event(event, match, parse_event_type)

    # ── 5. Synthesize HT / FT events ─────────────────────────────────
    if f["status"]["short"] == "HT":
        _ensure_synthetic_event(match, "HT", 45)
    elif f["status"]["short"] in ("FT", "AET", "PEN"):
        _ensure_synthetic_event(match, "FT", 90)


def _process_event(event: dict, match, parse_event_type):
    """Store a single match event and trigger alert if new."""
    from .models import MatchEvent, Team

    event_type = parse_event_type(event)
    minute = event["time"]["elapsed"]
    minute_extra = event["time"].get("extra")
    player_name = event.get("player", {}).get("name") or ""
    assist_name = event.get("assist", {}).get("name") or ""
    player_api_id = event.get("player", {}).get("id")
    assist_api_id = event.get("assist", {}).get("id")
    detail = event.get("detail") or ""
    comments = event.get("comments") or ""

    # Get team
    team = None
    if event.get("team", {}).get("id"):
        team, _ = Team.objects.get_or_create(
            api_id=event["team"]["id"],
            defaults={
                "name": event["team"]["name"],
                "logo_url": event["team"].get("logo") or "",
            },
        )

    # get_or_create prevents duplicates on re-fetch
    match_event, created = MatchEvent.objects.get_or_create(
        match=match,
        event_type=event_type,
        minute=minute,
        player_name=player_name,
        defaults={
            "team": team,
            "minute_extra": minute_extra,
            "assist_name": assist_name,
            "player_api_id": player_api_id,
            "assist_api_id": assist_api_id,
            "detail": detail,
            "comments": comments,
        },
    )

    # Only alert on genuinely new events
    if created and not match_event.alerted:
        _trigger_alert(match_event)


def _ensure_synthetic_event(match, event_type: str, minute: int):
    """Create HT/FT events that don't come from the events API."""
    from .models import MatchEvent

    event, created = MatchEvent.objects.get_or_create(
        match=match,
        event_type=event_type,
        minute=minute,
        player_name="",
    )
    if created:
        _trigger_alert(event)


def _trigger_alert(match_event):
    """Fire Celery task to send Telegram alerts for this event."""
    from apps.bot.push import send_match_event_alert
    send_match_event_alert.delay(match_event.pk)

    # Mark as alerted immediately to prevent race conditions
    match_event.alerted = True
    match_event.save(update_fields=["alerted"])


@shared_task(
    queue="critical",
    name="apps.matches.tasks.fetch_todays_fixtures",
)
def fetch_todays_fixtures():
    """
    Runs every 5 minutes via Celery Beat.
    Fetches today's scheduled fixtures so /scores and /fixtures commands
    have data even before matches go live.
    """
    from .poller import APIFootballClient, parse_event_type
    from .models import Match, Competition, Team
    from django.utils.dateparse import parse_datetime

    client = APIFootballClient()
    fixtures = client.get_todays_fixtures()

    created_count = 0
    for fixture in fixtures:
        f = fixture["fixture"]
        league = fixture["league"]
        teams = fixture["teams"]

        competition, _ = Competition.objects.get_or_create(
            api_id=league["id"],
            defaults={
                "name": league["name"],
                "country": league["country"],
                "logo_url": league.get("logo") or "",
                "flag_url": league.get("flag") or "",
                "season": league.get("season", 2026),
            },
        )
        home_team, _ = Team.objects.get_or_create(
            api_id=teams["home"]["id"],
            defaults={
                "name": teams["home"]["name"],
                "logo_url": teams["home"].get("logo") or "",
            },
        )
        away_team, _ = Team.objects.get_or_create(
            api_id=teams["away"]["id"],
            defaults={
                "name": teams["away"]["name"],
                "logo_url": teams["away"].get("logo") or "",
            },
        )

        _, created = Match.objects.get_or_create(
            api_id=f["id"],
            defaults={
                "competition": competition,
                "home_team": home_team,
                "away_team": away_team,
                "kickoff": parse_datetime(f["date"]),
                "venue": f.get("venue", {}).get("name") or "",
                "city": f.get("venue", {}).get("city") or "",
                "referee": f.get("referee") or "",
                "round": league.get("round") or "",
                "status": f["status"]["short"],
            },
        )
        if created:
            created_count += 1

    logger.info("Fetched today's fixtures: %d new", created_count)
    return f"created_{created_count}_fixtures"


@shared_task(
    queue="low",
    name="apps.matches.tasks.refresh_standings",
)
def refresh_standings():
    """
    Runs every 6 hours.
    Fetches standings for all tracked leagues and caches them in Redis.
    """
    from .poller import APIFootballClient
    from django.core.cache import cache

    client = APIFootballClient()

    LEAGUE_CODES = {
        39: "pl",
        2: "cl",
        140: "laliga",
        78: "bundesliga",
        135: "seriea",
        61: "ligue1",
        1: "worldcup",
    }

    for league_id, code in LEAGUE_CODES.items():
        data = client.get_standings(league_id)
        if not data:
            continue

        try:
            standings = data[0]["league"]["standings"][0]
            lines = [f"📊 *Standings — {data[0]['league']['name']}*\n"]
            for i, team in enumerate(standings[:20], 1):
                lines.append(
                    f"{i}. {team['team']['name']} — "
                    f"P{team['all']['played']} "
                    f"W{team['all']['win']} "
                    f"D{team['all']['draw']} "
                    f"L{team['all']['lose']} "
                    f"*{team['points']}pts*"
                )
            formatted = "\n".join(lines)
            # Cache for 6 hours
            cache.set(f"standings:{code}", formatted, timeout=60 * 60 * 6)
            logger.info("Standings cached for %s", code)
        except (KeyError, IndexError) as e:
            logger.error("Failed to parse standings for %s: %s", code, e)