import re
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from abtest.models import Visitor
from abtest.views import team_hash

BUTTON_RE = re.compile(r'<button id="abtest"[^>]*>\s*(kudos|thanks)\s*</button>')


class TeamHashTests(TestCase):
    def test_matches_course_example(self):
        # The course's worked example: printf %s bright-forest | shasum -> 211c220
        self.assertEqual(team_hash("bright-forest"), "211c220")

    def test_our_path(self):
        self.assertEqual(team_hash("sparkling-shape"), "e1531ff")
        self.assertEqual(reverse("ab_page"), "/e1531ff")
        self.assertEqual(reverse("ab_stats"), "/e1531ff/stats")


class ABPageTests(TestCase):
    def setUp(self):
        self.url = reverse("ab_page")

    def test_public_200_with_exactly_one_button(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertEqual(html.count('id="abtest"'), 1)
        self.assertRegex(html, BUTTON_RE)
        # Lists every team member (docs/mgt656/team.yaml).
        for nickname in ["smoggy-sheep", "gleaming-sheep", "sleepy-toad", "gentle-barracuda", "zany-seahorse"]:
            self.assertIn(nickname, html)

    def test_one_impression_and_sticky_variant_across_reloads(self):
        first = BUTTON_RE.search(self.client.get(self.url).content.decode()).group(1)
        for _ in range(3):
            again = BUTTON_RE.search(self.client.get(self.url).content.decode()).group(1)
            self.assertEqual(again, first)
        self.assertEqual(Visitor.objects.count(), 1)
        self.assertEqual(Visitor.objects.get().variant, first)

    def test_new_visitors_each_get_an_impression(self):
        for _ in range(4):
            self.client_class().get(self.url)
        self.assertEqual(Visitor.objects.count(), 4)

    def test_assignment_uses_both_variants(self):
        with mock.patch("abtest.views.choose_variant", side_effect=["kudos", "thanks"]):
            a = BUTTON_RE.search(self.client_class().get(self.url).content.decode()).group(1)
            b = BUTTON_RE.search(self.client_class().get(self.url).content.decode()).group(1)
        self.assertEqual({a, b}, {"kudos", "thanks"})

    def test_click_counts_once_and_redirect_is_not_an_impression(self):
        variant = BUTTON_RE.search(self.client.get(self.url).content.decode()).group(1)

        response = self.client.post(self.url, follow=True)
        self.assertEqual(response.redirect_chain[-1][0], self.url)
        self.assertEqual(BUTTON_RE.search(response.content.decode()).group(1), variant)

        self.client.post(self.url, follow=True)  # second click must not count

        visitor = Visitor.objects.get()
        self.assertIsNotNone(visitor.clicked_at)
        self.assertEqual(Visitor.objects.count(), 1)
        self.assertEqual(Visitor.objects.filter(clicked_at__isnull=False).count(), 1)

    def test_variant_is_server_rendered_not_javascript(self):
        html = self.client.get(self.url).content.decode()
        self.assertNotIn("<script", html)


class ABStatsTests(TestCase):
    def test_empty_stats(self):
        data = self.client.get(reverse("ab_stats")).json()
        self.assertIn(data["preferred"], {"kudos", "thanks"})
        self.assertEqual(data["kudos"], {"impressions": 0, "clicks": 0})

    def test_preferred_is_higher_click_rate_not_more_clicks(self):
        # kudos: 3 clicks / 10 impressions = 30% (more clicks)
        # thanks: 2 clicks / 4 impressions = 50% (higher rate, so preferred)
        now = timezone.now()
        for i in range(10):
            Visitor.objects.create(variant="kudos", clicked_at=now if i < 3 else None)
        for i in range(4):
            Visitor.objects.create(variant="thanks", clicked_at=now if i < 2 else None)

        data = self.client.get(reverse("ab_stats")).json()
        self.assertEqual(data["kudos"], {"impressions": 10, "clicks": 3})
        self.assertEqual(data["thanks"], {"impressions": 4, "clicks": 2})
        self.assertEqual(data["preferred"], "thanks")
