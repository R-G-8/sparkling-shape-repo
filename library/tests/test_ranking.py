import random
from itertools import combinations
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from library.models import Comparison, RankedTitle, Title
from library.ranking import InvalidPick, expected_score, next_pair, ranked_list, record_pick


def make_library(user, names):
    entries = []
    for name in names:
        title, _ = Title.objects.get_or_create(name=name)
        entries.append(RankedTitle.objects.create(user=user, title=title))
    return entries


class EloTests(TestCase):
    def test_expected_score(self):
        self.assertAlmostEqual(expected_score(1000, 1000), 0.5)
        self.assertAlmostEqual(expected_score(1400, 1000), 10 / 11)

    def test_pick_moves_ratings_and_records_comparison(self):
        user = get_user_model().objects.create_user("u")
        a, b = make_library(user, ["A", "B"])
        record_pick(user, a.title_id, b.title_id)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertAlmostEqual(a.rating, 1016)
        self.assertAlmostEqual(b.rating, 984)
        self.assertEqual((a.wins, a.losses, b.wins, b.losses), (1, 0, 0, 1))
        self.assertTrue(Comparison.objects.filter(user=user, winner=a.title, loser=b.title).exists())

    def test_cannot_pick_titles_outside_your_history(self):
        user = get_user_model().objects.create_user("u")
        other = get_user_model().objects.create_user("other")
        (mine,) = make_library(user, ["Mine"])
        (theirs,) = make_library(other, ["Theirs"])
        with self.assertRaises(InvalidPick):
            record_pick(user, mine.title_id, theirs.title_id)
        with self.assertRaises(InvalidPick):
            record_pick(user, mine.title_id, mine.title_id)
        self.assertEqual(Comparison.objects.count(), 0)


class NextPairTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("u")

    def test_needs_two_titles(self):
        self.assertIsNone(next_pair(self.user))
        make_library(self.user, ["Only one"])
        self.assertIsNone(next_pair(self.user))

    def test_two_different_titles_from_my_history(self):
        other = get_user_model().objects.create_user("other")
        make_library(other, ["Not mine 1", "Not mine 2"])
        mine = {e.title_id for e in make_library(self.user, ["A", "B", "C"])}
        for seed in range(10):
            a, b = next_pair(self.user, rng=random.Random(seed))
            self.assertNotEqual(a.title_id, b.title_id)
            self.assertTrue({a.title_id, b.title_id} <= mine)

    def test_covers_every_pair_before_repeating(self):
        entries = make_library(self.user, ["A", "B", "C", "D"])
        rng = random.Random(1)
        shown = set()
        for _ in range(len(list(combinations(entries, 2)))):
            a, b = next_pair(self.user, rng=rng)
            pair = frozenset((a.title_id, b.title_id))
            self.assertNotIn(pair, shown)
            shown.add(pair)
            record_pick(self.user, a.title_id, b.title_id)
        # Every pair is done; it keeps offering pairs rather than stopping.
        self.assertIsNotNone(next_pair(self.user, rng=rng))

    def test_skip_avoids_the_skipped_pair(self):
        a, b, c = make_library(self.user, ["A", "B", "C"])
        for seed in range(10):
            pair = next_pair(self.user, avoid=(a.title_id, b.title_id), rng=random.Random(seed))
            self.assertNotEqual({p.title_id for p in pair}, {a.title_id, b.title_id})


class RankingViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("u", password="a-long-unique-pw-9")
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()
        for name in ("rank", "my_ranking"):
            response = self.client.get(reverse(name))
            self.assertRedirects(response, f"{reverse('login')}?next={reverse(name)}")

    def test_without_history_points_to_import(self):
        response = self.client.get(reverse("rank"))
        self.assertContains(response, "at least two titles")
        self.assertContains(response, reverse("choose_service"))

    def test_shows_two_titles_with_pick_forms(self):
        make_library(self.user, ["Squid Game", "The Irishman"])
        html = self.client.get(reverse("rank")).content.decode()
        self.assertIn("Squid Game", html)
        self.assertIn("The Irishman", html)
        self.assertEqual(html.count('class="pick-card"'), 2)
        self.assertIn('id="pair"', html)  # swipe target
        self.assertIn("js/rank.js", html)

    def test_pick_records_and_shows_next_pair(self):
        a, b, c = make_library(self.user, ["A", "B", "C"])
        response = self.client.post(reverse("rank"), {"winner": a.title_id, "loser": b.title_id})
        self.assertRedirects(response, reverse("rank"))
        self.assertEqual(Comparison.objects.filter(user=self.user).count(), 1)
        html = self.client.get(reverse("rank")).content.decode()
        self.assertIn("1 pick so far", html)
        self.assertEqual(html.count('class="pick-card"'), 2)

    def test_bad_pick_is_rejected_politely(self):
        other = get_user_model().objects.create_user("other")
        (theirs,) = make_library(other, ["Theirs"])
        (mine,) = make_library(self.user, ["Mine"])
        response = self.client.post(reverse("rank"), {"winner": mine.title_id, "loser": theirs.title_id}, follow=True)
        self.assertContains(response, "That pick didn")
        response = self.client.post(reverse("rank"), {"winner": "x"}, follow=True)
        self.assertContains(response, "That pick didn")
        self.assertEqual(Comparison.objects.count(), 0)

    def test_ranked_list_orders_titles_by_my_picks(self):
        a, b, c, d = make_library(self.user, ["Alpha", "Bravo", "Charlie", "Delta"])
        # Charlie beats everyone, Alpha beats Bravo; Delta is never picked between.
        for winner, loser in [(c, a), (c, b), (a, b), (c, a)]:
            self.client.post(reverse("rank"), {"winner": winner.title_id, "loser": loser.title_id})
        self.assertEqual([e.title.name for e in ranked_list(self.user)], ["Charlie", "Alpha", "Bravo"])
        html = self.client.get(reverse("my_ranking")).content.decode()
        self.assertLess(html.index("Charlie"), html.index("Alpha"))
        self.assertLess(html.index("Alpha"), html.index("Bravo"))
        self.assertIn("1 more title not ranked yet", html)

    def test_ranked_list_is_per_user(self):
        other = get_user_model().objects.create_user("other")
        x, y = make_library(other, ["Xylophone Diaries", "Yonder Film"])
        record_pick(other, x.title_id, y.title_id)
        response = self.client.get(reverse("my_ranking"))
        self.assertNotContains(response, "Xylophone Diaries")
        self.assertNotContains(response, "Yonder Film")


class SwipeScriptTests(TestCase):
    def test_script_is_served_from_static(self):
        script = Path(settings.BASE_DIR) / "static" / "js" / "rank.js"
        source = script.read_text()
        self.assertIn("touchend", source)
        self.assertIn("ArrowLeft", source)
