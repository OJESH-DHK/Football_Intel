from django.db import models


TRACKED_LEAGUES = [2, 39, 61, 78, 135, 140, 1]

MATCH_STATUS = [
    ("TBD", "To Be Defined"),
    ("NS", "Not Started"),
    ("1H", "First Half"),
    ("HT", "Half Time"),
    ("2H", "Second Half"),
    ("ET", "Extra Time"),
    ("BT", "Break Time"),
    ("P", "Penalty"),
    ("SUSP", "Suspended"),
    ("INT", "Interrupted"),
    ("FT", "Full Time"),
    ("AET", "After Extra Time"),
    ("PEN", "Penalty Shootout"),
    ("PST", "Postponed"),
    ("CANC", "Cancelled"),
    ("ABD", "Abandoned"),
    ("AWD", "Technical Loss"),
    ("WO", "WalkOver"),
    ("LIVE", "Live"),
]

EVENT_TYPES = [
    ("GOAL", "Goal"),
    ("OWN_GOAL", "Own Goal"),
    ("PENALTY", "Penalty"),
    ("MISSED_PENALTY", "Missed Penalty"),
    ("YELLOW", "Yellow Card"),
    ("RED", "Red Card"),
    ("YELLOW_RED", "Second Yellow"),
    ("SUB", "Substitution"),
    ("VAR", "VAR Decision"),
    ("HT", "Half Time"),
    ("FT", "Full Time"),
]


class Competition(models.Model):
    api_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    logo_url = models.URLField(blank=True)
    flag_url = models.URLField(blank=True)
    season = models.IntegerField(default=2026)
    is_tracked = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.country})"


class Team(models.Model):
    api_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=50, blank=True)
    logo_url = models.URLField(blank=True)
    country = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.name


class Match(models.Model):
    # API reference
    api_id = models.IntegerField(unique=True, db_index=True)

    # Relations
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name="matches",
    )
    home_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="home_matches",
    )
    away_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="away_matches",
    )

    # Scores
    home_score = models.IntegerField(null=True, blank=True)
    away_score = models.IntegerField(null=True, blank=True)
    home_score_ht = models.IntegerField(null=True, blank=True)
    away_score_ht = models.IntegerField(null=True, blank=True)

    # Status
    status = models.CharField(max_length=10, choices=MATCH_STATUS, default="NS", db_index=True)
    minute = models.IntegerField(null=True, blank=True)

    # Timing
    kickoff = models.DateTimeField(db_index=True)
    venue = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    referee = models.CharField(max_length=100, blank=True)
    round = models.CharField(max_length=100, blank=True)

    # Tracking
    last_synced = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-kickoff"]
        indexes = [
            models.Index(fields=["status", "kickoff"]),
            models.Index(fields=["competition", "kickoff"]),
        ]

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} ({self.kickoff.date()})"

    @property
    def is_live(self):
        return self.status in ("1H", "2H", "ET", "HT", "BT", "P", "LIVE")

    @property
    def score_display(self):
        h = self.home_score if self.home_score is not None else "-"
        a = self.away_score if self.away_score is not None else "-"
        return f"{h} - {a}"


class MatchEvent(models.Model):
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="events",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="match_events",
        null=True,
        blank=True,
    )

    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    detail = models.CharField(max_length=100, blank=True)
    minute = models.IntegerField()
    minute_extra = models.IntegerField(null=True, blank=True)

    player_name = models.CharField(max_length=100, blank=True)
    player_api_id = models.IntegerField(null=True, blank=True)
    assist_name = models.CharField(max_length=100, blank=True)
    assist_api_id = models.IntegerField(null=True, blank=True)
    comments = models.TextField(blank=True)

    # Alert tracking — prevents duplicate Telegram pushes
    alerted = models.BooleanField(default=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["minute", "minute_extra"]
        # Prevents duplicate events from API re-fetches
        unique_together = ["match", "event_type", "minute", "player_name"]

    def __str__(self):
        return f"{self.match} | {self.event_type} {self.minute}' {self.player_name}"

    def alert_emoji(self):
        return {
            "GOAL": "⚽",
            "OWN_GOAL": "⚽ OG",
            "PENALTY": "⚽ PEN",
            "MISSED_PENALTY": "❌ PEN",
            "YELLOW": "🟨",
            "RED": "🟥",
            "YELLOW_RED": "🟥",
            "SUB": "🔄",
            "VAR": "📺",
            "HT": "🔔",
            "FT": "🏁",
        }.get(self.event_type, "•")

    def format_alert(self):
        """Returns formatted Telegram alert message for this event."""
        match = self.match
        emoji = self.alert_emoji()
        minute = f"{self.minute}'{f'+{self.minute_extra}' if self.minute_extra else ''}"

        if self.event_type in ("GOAL", "OWN_GOAL", "PENALTY"):
            return (
                f"{emoji} *GOAL!*\n"
                f"*{match.home_team.name} {match.score_display} {match.away_team.name}*\n"
                f"{self.player_name} ({self.team.name}) {minute}\n"
                f"🏆 {match.competition.name}"
            )
        elif self.event_type in ("YELLOW", "RED", "YELLOW_RED"):
            card = {"YELLOW": "Yellow Card", "RED": "RED CARD", "YELLOW_RED": "2nd Yellow → Red"}[self.event_type]
            return (
                f"{emoji} *{card}*\n"
                f"{self.player_name} ({self.team.name}) {minute}\n"
                f"{match.home_team.name} vs {match.away_team.name}\n"
                f"🏆 {match.competition.name}"
            )
        elif self.event_type == "SUB":
            return (
                f"{emoji} *Substitution* {minute}\n"
                f"🔺 {self.assist_name} → 🔻 {self.player_name}\n"
                f"{self.team.name}"
            )
        elif self.event_type == "HT":
            return (
                f"🔔 *Half Time*\n"
                f"*{match.home_team.name} {match.score_display} {match.away_team.name}*\n"
                f"🏆 {match.competition.name}"
            )
        elif self.event_type == "FT":
            return (
                f"🏁 *Full Time*\n"
                f"*{match.home_team.name} {match.score_display} {match.away_team.name}*\n"
                f"🏆 {match.competition.name}"
            )
        return f"{emoji} {self.event_type} — {match.home_team.name} vs {match.away_team.name}"