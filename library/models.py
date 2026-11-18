from django.conf import settings
from django.db import models


class Title(models.Model):
    """A show or film, shared by every user.

    Netflix lists each episode separately ("Show: Season 1: Pilot"); those rows
    all point at one Title for the show, so users rank shows rather than episodes.
    """

    name = models.CharField(max_length=500, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ViewingActivity(models.Model):
    """One row of an imported watch-history file (what was watched, and when)."""

    NETFLIX = "netflix"
    SERVICE_CHOICES = [(NETFLIX, "Netflix")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="viewing_activity")
    title = models.ForeignKey(Title, on_delete=models.CASCADE, related_name="viewings")
    raw_title = models.CharField(max_length=500, help_text="The title exactly as it appeared in the file.")
    watched_on = models.DateField()
    service = models.CharField(max_length=20, choices=SERVICE_CHOICES, default=NETFLIX)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "viewing activity"
        ordering = ["-watched_on", "raw_title"]
        constraints = [
            # Re-uploading the same file must not create duplicates.
            models.UniqueConstraint(
                fields=["user", "service", "raw_title", "watched_on"], name="unique_viewing_per_user"
            )
        ]

    def __str__(self):
        return f"{self.raw_title} ({self.watched_on})"


class RankedTitle(models.Model):
    """A title in one user's personal ranking, with an Elo rating from their picks."""

    INITIAL_RATING = 1000.0

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ranked_titles")
    title = models.ForeignKey(Title, on_delete=models.CASCADE, related_name="rankings")
    rating = models.FloatField(default=INITIAL_RATING)
    wins = models.PositiveIntegerField(default=0)
    losses = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "title"], name="unique_ranked_title_per_user")]
        indexes = [models.Index(fields=["user", "-rating"])]

    def __str__(self):
        return f"{self.title} ({self.rating:.0f})"

    @property
    def comparisons(self):
        return self.wins + self.losses


class Comparison(models.Model):
    """One pick on the ranking screen: the user liked `winner` more than `loser`."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comparisons")
    winner = models.ForeignKey(Title, on_delete=models.CASCADE, related_name="+")
    loser = models.ForeignKey(Title, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=~models.Q(winner=models.F("loser")), name="comparison_distinct_titles")
        ]

    def __str__(self):
        return f"{self.winner} > {self.loser}"
