from django.db import models


class TelegramUser(models.Model):
    telegram_id = models.BigIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=100, blank=True)
    first_name = models.CharField(max_length=100, blank=True)

    # Personalisation — follows Teams from matches app
    followed_teams = models.ManyToManyField(
        "matches.Team",
        blank=True,
        related_name="followers",
    )

    # Alert preferences
    alert_goals = models.BooleanField(default=True)
    alert_cards = models.BooleanField(default=True)
    alert_news_digest = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Telegram User"
        verbose_name_plural = "Telegram Users"

    def __str__(self):
        return f"@{self.username or self.telegram_id}"


class Bookmark(models.Model):
    user = models.ForeignKey(
        TelegramUser,
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    # Will link to Article model when news feature is built
    article_id = models.IntegerField()
    article_title = models.CharField(max_length=300)
    article_url = models.URLField()
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "article_id")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} → {self.article_title[:50]}"