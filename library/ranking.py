"""
Pairwise ranking: show two titles, the user picks the one they liked more.

Each pick updates both titles' Elo ratings, so the ranked list is simply the
user's titles ordered by rating. Pairs favour titles with the fewest picks so
far, and among those, titles with close ratings (the most informative match-up).
"""

import random

from django.db import transaction

from .models import Comparison, RankedTitle

K_FACTOR = 32


class InvalidPick(Exception):
    pass


def expected_score(rating, opponent_rating):
    """Probability that a title rated `rating` beats one rated `opponent_rating`."""
    return 1 / (1 + 10 ** ((opponent_rating - rating) / 400))


def next_pair(user, avoid=None, rng=random):
    """Two of the user's RankedTitles to compare, or None if they have fewer than two.

    `avoid` is a pair of title ids (e.g. the pair the user just skipped) not to
    show again straight away, when there is any other choice.
    """
    entries = list(RankedTitle.objects.filter(user=user).select_related("title"))
    if len(entries) < 2:
        return None

    seen = {frozenset(pair) for pair in Comparison.objects.filter(user=user).values_list("winner_id", "loser_id")}
    skip = frozenset(avoid) if avoid else None

    rng.shuffle(entries)  # random order among ties
    entries.sort(key=lambda entry: entry.comparisons)

    def key(pair):
        return frozenset((pair[0].title_id, pair[1].title_id))

    for first in entries:
        options = [other for other in entries if other is not first]
        fresh = [other for other in options if key((first, other)) not in seen and key((first, other)) != skip]
        if fresh:
            second = min(fresh, key=lambda other: (other.comparisons, abs(other.rating - first.rating)))
            return _shuffled(first, second, rng)

    # Every pair has been compared: re-check the closest-rated pair the user didn't just skip.
    by_rating = sorted(entries, key=lambda entry: entry.rating)
    neighbours = [pair for pair in zip(by_rating, by_rating[1:]) if key(pair) != skip] or list(
        zip(by_rating, by_rating[1:])
    )
    first, second = min(neighbours, key=lambda pair: abs(pair[0].rating - pair[1].rating))
    return _shuffled(first, second, rng)


def _shuffled(first, second, rng):
    pair = [first, second]
    rng.shuffle(pair)
    return tuple(pair)


@transaction.atomic
def record_pick(user, winner_title_id, loser_title_id):
    """Record that `user` liked the winner more than the loser, and update ratings."""
    if winner_title_id == loser_title_id:
        raise InvalidPick("Pick between two different titles.")
    entries = {
        entry.title_id: entry
        for entry in RankedTitle.objects.select_for_update().filter(
            user=user, title_id__in=[winner_title_id, loser_title_id]
        )
    }
    if len(entries) != 2:
        raise InvalidPick("Both titles must be in your watch history.")

    winner, loser = entries[winner_title_id], entries[loser_title_id]
    change = K_FACTOR * (1 - expected_score(winner.rating, loser.rating))
    winner.rating += change
    winner.wins += 1
    loser.rating -= change
    loser.losses += 1
    winner.save(update_fields=["rating", "wins"])
    loser.save(update_fields=["rating", "losses"])
    return Comparison.objects.create(user=user, winner_id=winner_title_id, loser_id=loser_title_id)


def ranked_list(user):
    """The user's titles that have been in at least one pick, best first."""
    return (
        RankedTitle.objects.filter(user=user)
        .exclude(wins=0, losses=0)
        .select_related("title")
        .order_by("-rating", "-wins", "title__name")
    )
