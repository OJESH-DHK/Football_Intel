import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

app = Celery("football_intel")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    from celery.schedules import crontab

    # ── Live score poller — every 60 seconds ─────────────────────────
    sender.add_periodic_task(
        60.0,
        app.signature("apps.matches.tasks.poll_live_scores"),
        name="poll live scores every 60s",
        queue="critical",
    )

    # ── Today's fixtures — every 5 minutes ───────────────────────────
    sender.add_periodic_task(
        300.0,
        app.signature("apps.matches.tasks.fetch_todays_fixtures"),
        name="fetch todays fixtures every 5min",
        queue="default",
    )

    # ── Standings — every 6 hours ─────────────────────────────────────
    sender.add_periodic_task(
        crontab(minute=0, hour="*/6"),
        app.signature("apps.matches.tasks.refresh_standings"),
        name="refresh standings every 6h",
        queue="low",
    )