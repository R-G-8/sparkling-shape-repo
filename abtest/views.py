import hashlib
import secrets

from django.conf import settings
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from .models import Visitor

SESSION_KEY = "abtest_visitor_id"


def team_hash(nickname=None):
    """First 7 hex chars of SHA-1 of the team nickname (no trailing newline)."""
    nickname = settings.TEAM_NICKNAME if nickname is None else nickname
    return hashlib.sha1(nickname.encode("utf-8")).hexdigest()[:7]


def choose_variant():
    """Pick kudos or thanks uniformly at random (50/50)."""
    return secrets.choice([Visitor.KUDOS, Visitor.THANKS])


def _current_visitor(request):
    visitor_id = request.session.get(SESSION_KEY)
    if not visitor_id:
        return None
    return Visitor.objects.filter(pk=visitor_id).first()


@never_cache
@require_http_methods(["GET", "POST"])
def ab_page(request):
    visitor = _current_visitor(request)

    if request.method == "POST":
        # Count at most one click per visitor; the filter makes this atomic.
        if visitor is not None:
            Visitor.objects.filter(pk=visitor.pk, clicked_at__isnull=True).update(
                clicked_at=timezone.now()
            )
        # Redirect back with GET; the session keeps the same visitor, so no new impression.
        return redirect(request.path)

    if visitor is None:
        # First view: assign a variant 50/50 and record the impression.
        visitor = Visitor.objects.create(variant=choose_variant())
        request.session[SESSION_KEY] = str(visitor.pk)

    return render(
        request,
        "abtest/page.html",
        {
            "variant": visitor.variant,
            "clicked": visitor.clicked_at is not None,
            "members": settings.TEAM_MEMBER_NICKNAMES,
            "team_nickname": settings.TEAM_NICKNAME,
        },
    )


@never_cache
@require_GET
def ab_stats(request):
    counts = {}
    for variant in (Visitor.KUDOS, Visitor.THANKS):
        agg = Visitor.objects.filter(variant=variant).aggregate(
            impressions=Count("pk"),
            clicks=Count("pk", filter=Q(clicked_at__isnull=False)),
        )
        counts[variant] = {"impressions": agg["impressions"], "clicks": agg["clicks"]}

    def rate(variant):
        c = counts[variant]
        return c["clicks"] / c["impressions"] if c["impressions"] else 0.0

    # Ties (including no data) default to kudos.
    preferred = Visitor.THANKS if rate(Visitor.THANKS) > rate(Visitor.KUDOS) else Visitor.KUDOS
    return JsonResponse({"preferred": preferred, **counts})
