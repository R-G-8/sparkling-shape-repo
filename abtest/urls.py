from django.urls import path

from . import views

HASH = views.team_hash()

urlpatterns = [
    path(f"{HASH}", views.ab_page, name="ab_page"),
    path(f"{HASH}/stats", views.ab_stats, name="ab_stats"),
]
