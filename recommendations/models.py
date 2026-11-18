from django.conf import settings
from django.db import models


class RecommendationSet(models.Model):
    """One LLM call's worth of recommendations for a user. The newest set is shown."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recommendation_sets")
    model = models.CharField(max_length=200, help_text="The OpenRouter model that answered.")
    based_on = models.JSONField(default=list, help_text="The titles we sent to the model.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def __str__(self):
        return f"Recommendations for {self.user} at {self.created_at:%Y-%m-%d %H:%M}"


class Recommendation(models.Model):
    KIND_CHOICES = [("movie", "Movie"), ("series", "Series")]

    recommendation_set = models.ForeignKey(RecommendationSet, on_delete=models.CASCADE, related_name="items")
    position = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, blank=True)
    reason = models.CharField(max_length=300)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return self.title
