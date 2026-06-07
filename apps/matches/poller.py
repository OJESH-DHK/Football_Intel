import logging
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://v3.football.api-sports.io"
TRACKED_LEAGUES = [2, 39, 61, 78, 135, 140, 1]

HEADERS = {
    "x-apisports-key": settings.API_FOOTBALL_KEY,
}


class APIFootballClient:

    def get_live_fixtures(self):
        """Fetch all currently live matches."""
        try:
            r = httpx.get(
                f"{BASE_URL}/fixtures",
                headers=HEADERS,
                params={"live": "all"},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            # Filter to only our tracked leagues
            return [
                f for f in data.get("response", [])
                if f["league"]["id"] in TRACKED_LEAGUES
            ]
        except Exception as e:
            logger.error("Failed to fetch live fixtures: %s", e)
            return []

    def get_todays_fixtures(self):
        """Fetch all fixtures for today across tracked leagues."""
        from datetime import date
        today = date.today().isoformat()
        results = []
        try:
            for league_id in TRACKED_LEAGUES:
                r = httpx.get(
                    f"{BASE_URL}/fixtures",
                    headers=HEADERS,
                    params={"league": league_id, "date": today, "season": 2026},
                    timeout=15,
                )
                r.raise_for_status()
                results.extend(r.json().get("response", []))
        except Exception as e:
            logger.error("Failed to fetch today's fixtures: %s", e)
        return results

    def get_fixture_events(self, fixture_id: int):
        """Fetch all events for a specific fixture."""
        try:
            r = httpx.get(
                f"{BASE_URL}/fixtures/events",
                headers=HEADERS,
                params={"fixture": fixture_id},
                timeout=15,
            )
            r.raise_for_status()
            return r.json().get("response", [])
        except Exception as e:
            logger.error("Failed to fetch events for fixture %s: %s", fixture_id, e)
            return []

    def get_standings(self, league_id: int, season: int = 2026):
        """Fetch standings for a league."""
        try:
            r = httpx.get(
                f"{BASE_URL}/standings",
                headers=HEADERS,
                params={"league": league_id, "season": season},
                timeout=15,
            )
            r.raise_for_status()
            return r.json().get("response", [])
        except Exception as e:
            logger.error("Failed to fetch standings for league %s: %s", league_id, e)
            return []


def parse_event_type(event: dict) -> str:
    """Map API-Football event type/detail to our EVENT_TYPES."""
    etype = event.get("type", "")
    detail = event.get("detail", "")

    if etype == "Goal":
        if detail == "Own Goal":
            return "OWN_GOAL"
        elif detail == "Penalty":
            return "PENALTY"
        elif detail == "Missed Penalty":
            return "MISSED_PENALTY"
        return "GOAL"
    elif etype == "Card":
        if detail == "Yellow Card":
            return "YELLOW"
        elif detail == "Red Card":
            return "RED"
        elif detail == "Second Yellow card":
            return "YELLOW_RED"
    elif etype == "subst":
        return "SUB"
    elif etype == "Var":
        return "VAR"

    return etype.upper()