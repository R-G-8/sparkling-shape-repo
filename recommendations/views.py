from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from library.models import ViewingActivity

from .models import RecommendationSet
from .services import RecommendationError, generate_recommendations


@login_required
@require_http_methods(["GET", "POST"])
def recommendations(request):
    if request.method == "POST":
        try:
            generate_recommendations(request.user)
        except RecommendationError as exc:
            messages.error(request, str(exc))
        return redirect("recommendations")

    latest = RecommendationSet.objects.filter(user=request.user).prefetch_related("items").first()
    has_history = ViewingActivity.objects.filter(user=request.user).exists()
    return render(
        request,
        "recommendations/recommendations.html",
        {"latest": latest, "has_history": has_history},
    )
