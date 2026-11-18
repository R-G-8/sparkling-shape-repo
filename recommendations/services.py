"""
Turn a user's rankings into AI recommendations.

We send the user's top-ranked titles (or, before they've ranked, their most
watched) and their services to the LLM, ask for JSON matching a schema, then
check every item ourselves: titles already in the user's history are dropped,
reasons are cut to one line, and we need at least MIN_RECOMMENDATIONS left.
"""

import json
import logging
import re
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from library.models import RankedTitle, ViewingActivity

from . import openrouter
from .models import Recommendation, RecommendationSet

logger = logging.getLogger(__name__)

ASK_FOR = 10
MIN_RECOMMENDATIONS = 5
MAX_INPUT_TITLES = 15
MAX_REASON_LENGTH = 160

RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "recommendations",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "year": {"type": ["integer", "null"]},
                            "kind": {"type": "string", "enum": ["movie", "series"]},
                            "reason": {"type": "string"},
                        },
                        "required": ["title", "year", "kind", "reason"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["recommendations"],
            "additionalProperties": False,
        },
    },
}


class RecommendationError(Exception):
    """Shown to the user as-is, so keep messages friendly."""


def normalize(title):
    """Loose key for matching titles: case, punctuation and a leading "the" don't matter."""
    key = re.sub(r"[^0-9a-z]+", " ", title.casefold()).strip()
    return re.sub(r"^the ", "", key)


def input_titles(user):
    """The titles we describe the user's taste with: top-ranked first, then most watched."""
    ranked = (
        RankedTitle.objects.filter(user=user)
        .exclude(wins=0, losses=0)
        .select_related("title")
        .order_by("-rating", "-wins")[:MAX_INPUT_TITLES]
    )
    names = [entry.title.name for entry in ranked]
    if len(names) < MAX_INPUT_TITLES:
        most_watched = (
            ViewingActivity.objects.filter(user=user)
            .values("title__name")
            .annotate(views=Count("id"))
            .order_by("-views", "title__name")[: MAX_INPUT_TITLES * 2]
        )
        for row in most_watched:
            if row["title__name"] not in names:
                names.append(row["title__name"])
            if len(names) >= MAX_INPUT_TITLES:
                break
    return names, len(ranked)


def user_services(user):
    labels = dict(ViewingActivity.SERVICE_CHOICES)
    services = ViewingActivity.objects.filter(user=user).values_list("service", flat=True).distinct()
    return sorted(labels.get(service, service) for service in services)


def build_messages(titles, ranked_count, services):
    if ranked_count:
        taste = f"Their favourites, best first (from their own head-to-head rankings): {json.dumps(titles)}"
    else:
        taste = f"Titles they have watched most: {json.dumps(titles)}"
    return [
        {
            "role": "system",
            "content": (
                "You recommend films and TV series. Reply with JSON only, matching the schema. "
                "Each reason is one short sentence (under 20 words) that names what the user "
                "liked and why this title fits."
            ),
        },
        {
            "role": "user",
            "content": (
                f"{taste}\n"
                f"They subscribe to: {', '.join(services) or 'Netflix'}. Prefer titles on those services.\n"
                f"Recommend {ASK_FOR} real titles they have not seen. Do not include any title from the "
                "list above, or other seasons or episodes of those shows."
            ),
        },
    ]


def parse_recommendations(content):
    """Pull the list of recommendation dicts out of the model's reply."""
    text = content.strip()
    # Some models wrap JSON in a ```json fence despite instructions.
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in reply")
    data = json.loads(text[start : end + 1])
    items = data.get("recommendations") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("reply has no recommendations list")
    return items


def clean_items(items, history_keys):
    """Validate the model's items and drop anything already watched or repeated."""
    cleaned, seen = [], set(history_keys)
    for item in items:
        if not isinstance(item, dict):
            continue
        title = " ".join(str(item.get("title") or "").split())[:200]
        reason = " ".join(str(item.get("reason") or "").split())
        if not title or not reason:
            continue
        key = normalize(title)
        if not key or key in seen:
            continue
        seen.add(key)
        if len(reason) > MAX_REASON_LENGTH:
            reason = reason[: MAX_REASON_LENGTH - 1].rstrip() + "…"
        year = item.get("year")
        year = year if isinstance(year, int) and 1880 <= year <= 2100 else None
        kind = item.get("kind") if item.get("kind") in ("movie", "series") else ""
        cleaned.append({"title": title, "year": year, "kind": kind, "reason": reason})
    return cleaned


def history_keys(user):
    keys = {normalize(name) for name in RankedTitle.objects.filter(user=user).values_list("title__name", flat=True)}
    keys.update(
        normalize(raw) for raw in ViewingActivity.objects.filter(user=user).values_list("raw_title", flat=True)
    )
    return keys


def calls_today(user):
    since = timezone.now() - timedelta(days=1)
    return RecommendationSet.objects.filter(user=user, created_at__gte=since).count()


def generate_recommendations(user):
    """Call the LLM and save a new RecommendationSet, or raise RecommendationError."""
    titles, ranked_count = input_titles(user)
    if not titles:
        raise RecommendationError("Import your watch history first, so we know what you like.")

    limit = settings.RECOMMENDATIONS_DAILY_LIMIT
    if calls_today(user) >= limit:
        raise RecommendationError(
            f"You've asked for recommendations {limit} times in the last 24 hours. Try again tomorrow."
        )

    try:
        content, model = openrouter.chat_completion(
            build_messages(titles, ranked_count, user_services(user)), response_format=RESPONSE_SCHEMA
        )
        items = parse_recommendations(content)
    except openrouter.LLMNotConfigured:
        logger.warning("recommendations requested but OPENROUTER_API_KEY is not set")
        raise RecommendationError("Recommendations aren't switched on yet. Please try again later.")
    except (openrouter.LLMError, ValueError) as exc:
        logger.warning("recommendations failed for user=%s: %s", user.pk, exc)
        raise RecommendationError("We couldn't get recommendations right now. Please try again in a minute.")

    cleaned = clean_items(items, history_keys(user))
    if len(cleaned) < MIN_RECOMMENDATIONS:
        logger.warning("recommendations for user=%s: only %s usable of %s", user.pk, len(cleaned), len(items))
        raise RecommendationError("We couldn't get enough new recommendations this time. Please try again.")

    with transaction.atomic():
        rec_set = RecommendationSet.objects.create(user=user, model=model[:200], based_on=titles)
        Recommendation.objects.bulk_create(
            [Recommendation(recommendation_set=rec_set, position=i, **item) for i, item in enumerate(cleaned, 1)]
        )
    return rec_set
