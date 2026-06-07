from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .models import Competition, Match, MatchEvent

# Statuses that count as a match being in progress.
LIVE_STATUSES = ["1H", "2H", "ET", "HT", "BT", "P", "LIVE"]
# Statuses for matches that have not kicked off yet.
SCHEDULED_STATUSES = ["NS", "TBD"]


def _dashboard_stats():
    """Top-of-page stat cards: matches today, live now, events today."""
    today = timezone.localdate()
    return {
        "matches_today": Match.objects.filter(kickoff__date=today).count(),
        "live_now": Match.objects.filter(status__in=LIVE_STATUSES).count(),
        "events_today": MatchEvent.objects.filter(match__kickoff__date=today).count(),
    }


@login_required
def live_matches(request):
    matches = (
        Match.objects.filter(status__in=LIVE_STATUSES)
        .select_related("home_team", "away_team", "competition")
        .prefetch_related("events__team")
        .order_by("competition__name", "kickoff")
    )
    return render(
        request,
        "matches/live.html",
        {
            "stats": _dashboard_stats(),
            "matches": matches,
            "active": "live",
        },
    )


@login_required
def fixtures(request):
    today = timezone.localdate()
    matches = (
        Match.objects.filter(kickoff__date=today, status__in=SCHEDULED_STATUSES)
        .select_related("home_team", "away_team", "competition")
        .order_by("competition__name", "kickoff")
    )

    # Group by competition, preserving query order.
    groups = {}
    for match in matches:
        groups.setdefault(match.competition, []).append(match)

    grouped = [{"competition": comp, "matches": ms} for comp, ms in groups.items()]

    return render(
        request,
        "matches/fixtures.html",
        {
            "stats": _dashboard_stats(),
            "grouped": grouped,
            "today": today,
            "active": "fixtures",
        },
    )


@login_required
def match_detail(request, pk):
    match = get_object_or_404(
        Match.objects.select_related("home_team", "away_team", "competition"),
        pk=pk,
    )
    events = match.events.select_related("team").order_by("minute", "minute_extra")
    return render(
        request,
        "matches/match_detail.html",
        {
            "stats": _dashboard_stats(),
            "match": match,
            "events": events,
            "active": "live",
        },
    )


@login_required
def competitions(request):
    today = timezone.localdate()
    comps = (
        Competition.objects.filter(is_tracked=True)
        .annotate(
            match_count=Count("matches"),
            live_count=Count("matches", filter=Q(matches__status__in=LIVE_STATUSES)),
            today_count=Count("matches", filter=Q(matches__kickoff__date=today)),
        )
        .order_by("country", "name")
    )
    return render(
        request,
        "matches/competitions.html",
        {
            "stats": _dashboard_stats(),
            "competitions": comps,
            "active": "competitions",
        },
    )
