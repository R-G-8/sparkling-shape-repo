import uuid

from django.db import models


class Visitor(models.Model):
    """One A/B test visitor.

    Creating the row is the visitor's single impression; clicked_at is set at
    most once, the first time they click the button.
    """

    KUDOS = "kudos"
    THANKS = "thanks"
    VARIANT_CHOICES = [(KUDOS, "kudos"), (THANKS, "thanks")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.CharField(max_length=6, choices=VARIANT_CHOICES)
    impression_at = models.DateTimeField(auto_now_add=True)
    clicked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["variant"])]

    def __str__(self):
        return f"{self.variant} visitor {self.id}"
