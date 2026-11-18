import io
import json
import urllib.error
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from library.importers import import_viewing_history
from library.models import RankedTitle
from library.ranking import record_pick
from recommendations import openrouter
from recommendations.models import Recommendation, RecommendationSet
from recommendations.services import (
    RecommendationError,
    clean_items,
    generate_recommendations,
    normalize,
    parse_recommendations,
)

HISTORY = [
    ("Squid Game: Season 1: Red Light, Green Light", date(2021, 9, 17)),
    ("Squid Game: Season 1: Hell", date(2021, 9, 18)),
    ("The Irishman", date(2019, 11, 29)),
    ("Dark: Season 1: Secrets", date(2020, 1, 1)),
]

NEW_TITLES = ["Alice in Borderland", "Mindhunter", "Severance", "The Good Place", "Narcos", "Kingdom", "Ozark"]


def llm_reply(titles, extra=()):
    items = [{"title": t, "year": 2020, "kind": "series", "reason": f"Because you liked Squid Game: {t}."} for t in titles]
    items.extend(extra)
    return json.dumps({"recommendations": items}), "test/model"


class ParsingTests(TestCase):
    def test_parses_plain_and_fenced_json(self):
        body = json.dumps({"recommendations": [{"title": "X", "reason": "Y"}]})
        self.assertEqual(parse_recommendations(body)[0]["title"], "X")
        self.assertEqual(parse_recommendations(f"```json\n{body}\n```")[0]["title"], "X")

    def test_rejects_non_json(self):
        for content in ["Sorry, I can't help", "{not json}", json.dumps({"recs": []})]:
            with self.assertRaises(ValueError):
                parse_recommendations(content)

    def test_normalize(self):
        self.assertEqual(normalize("The Irishman"), normalize("irishman"))
        self.assertEqual(normalize("Squid  Game!"), normalize("squid game"))

    def test_clean_items_drops_watched_duplicates_and_junk(self):
        items = [
            {"title": "Squid Game", "reason": "Watched already"},
            {"title": "Severance", "year": 2022, "kind": "series", "reason": "Fits.\nSecond line."},
            {"title": "severance", "reason": "Duplicate"},
            {"title": "", "reason": "No title"},
            {"title": "No reason"},
            "not a dict",
            {"title": "Roma", "year": "1999", "kind": "film", "reason": "x" * 400},
        ]
        cleaned = clean_items(items, {normalize("Squid Game")})
        self.assertEqual([c["title"] for c in cleaned], ["Severance", "Roma"])
        self.assertEqual(cleaned[0]["reason"], "Fits. Second line.")  # one line
        self.assertEqual(cleaned[1]["year"], None)
        self.assertEqual(cleaned[1]["kind"], "")
        self.assertLessEqual(len(cleaned[1]["reason"]), 160)


@override_settings(OPENROUTER_API_KEY="test-key", RECOMMENDATIONS_DAILY_LIMIT=3)
class GenerateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("u", password="a-long-unique-pw-9")
        import_viewing_history(self.user, HISTORY)
        squid, irishman = (RankedTitle.objects.get(user=self.user, title__name=n) for n in ("Squid Game", "The Irishman"))
        record_pick(self.user, squid.title_id, irishman.title_id)

    @mock.patch("recommendations.services.openrouter.chat_completion")
    def test_saves_recommendations_excluding_history(self, chat):
        chat.return_value = llm_reply(NEW_TITLES, extra=[{"title": "Squid Game", "year": 2021, "kind": "series", "reason": "x"}])
        rec_set = generate_recommendations(self.user)
        titles = list(rec_set.items.values_list("title", flat=True))
        self.assertEqual(titles, NEW_TITLES)
        self.assertNotIn("Squid Game", titles)
        self.assertEqual(rec_set.model, "test/model")
        self.assertEqual(rec_set.based_on[0], "Squid Game")  # top-ranked first

        messages = chat.call_args.args[0]
        prompt = messages[-1]["content"]
        self.assertIn("Squid Game", prompt)
        self.assertIn("Netflix", prompt)
        self.assertEqual(chat.call_args.kwargs["response_format"]["type"], "json_schema")

    @mock.patch("recommendations.services.openrouter.chat_completion")
    def test_too_few_new_titles_is_an_error(self, chat):
        chat.return_value = llm_reply(NEW_TITLES[:3] + ["Squid Game", "The Irishman", "Dark"])
        with self.assertRaises(RecommendationError):
            generate_recommendations(self.user)
        self.assertEqual(RecommendationSet.objects.count(), 0)

    @mock.patch("recommendations.services.openrouter.chat_completion")
    def test_llm_failure_is_a_friendly_error(self, chat):
        for failure in [openrouter.LLMError("HTTP 502"), None]:
            chat.side_effect = failure
            chat.return_value = ("I can't do that", "m")
            with self.assertRaises(RecommendationError) as ctx:
                generate_recommendations(self.user)
            self.assertIn("try again", str(ctx.exception))
        self.assertEqual(RecommendationSet.objects.count(), 0)

    @mock.patch("recommendations.services.openrouter.chat_completion")
    def test_daily_limit(self, chat):
        chat.return_value = llm_reply(NEW_TITLES)
        for _ in range(3):
            generate_recommendations(self.user)
        with self.assertRaises(RecommendationError) as ctx:
            generate_recommendations(self.user)
        self.assertIn("3 times", str(ctx.exception))
        self.assertEqual(chat.call_count, 3)

    @mock.patch("recommendations.services.openrouter.chat_completion")
    def test_no_history_means_no_llm_call(self, chat):
        empty = get_user_model().objects.create_user("empty")
        with self.assertRaises(RecommendationError):
            generate_recommendations(empty)
        chat.assert_not_called()


@override_settings(OPENROUTER_API_KEY="test-key")
class ViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("u", password="a-long-unique-pw-9")
        self.client.force_login(self.user)
        self.url = reverse("recommendations")

    def test_requires_login(self):
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), f"{reverse('login')}?next={self.url}")

    def test_without_history_points_to_import(self):
        self.assertContains(self.client.get(self.url), reverse("choose_service"))

    @mock.patch("recommendations.services.openrouter.chat_completion")
    def test_shows_at_least_five_with_reasons(self, chat):
        import_viewing_history(self.user, HISTORY)
        chat.return_value = llm_reply(NEW_TITLES)
        response = self.client.post(self.url, follow=True)
        self.assertRedirects(response, self.url)
        html = response.content.decode()
        for title in NEW_TITLES:
            self.assertIn(title, html)
            self.assertIn(f"Because you liked Squid Game: {title}.", html)
        self.assertEqual(Recommendation.objects.count(), len(NEW_TITLES))

    @mock.patch("recommendations.services.openrouter.chat_completion", side_effect=openrouter.LLMError("boom"))
    def test_failure_shows_friendly_message_not_a_crash(self, chat):
        import_viewing_history(self.user, HISTORY)
        response = self.client.post(self.url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "We couldn&#x27;t get recommendations right now")

    @override_settings(OPENROUTER_API_KEY="")
    def test_missing_key_is_friendly(self):
        import_viewing_history(self.user, HISTORY)
        with mock.patch("urllib.request.urlopen") as urlopen:
            response = self.client.post(self.url, follow=True)
        urlopen.assert_not_called()
        self.assertContains(response, "switched on yet")


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@override_settings(OPENROUTER_API_KEY="sk-test", OPENROUTER_MODEL="vendor/model", OPENROUTER_TIMEOUT_SECONDS=5)
class OpenRouterClientTests(TestCase):
    """The HTTP client itself, with urlopen mocked: no network calls."""

    @mock.patch("recommendations.openrouter.urllib.request.urlopen")
    def test_sends_key_model_and_schema_from_the_server(self, urlopen):
        urlopen.return_value = FakeResponse(
            json.dumps({"model": "vendor/model", "choices": [{"message": {"content": "{}"}}]}).encode()
        )
        content, model = openrouter.chat_completion([{"role": "user", "content": "hi"}], response_format={"type": "json_object"})
        self.assertEqual((content, model), ("{}", "vendor/model"))
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, openrouter.API_URL)
        self.assertEqual(request.get_header("Authorization"), "Bearer sk-test")
        body = json.loads(request.data)
        self.assertEqual(body["model"], "vendor/model")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 5)

    @mock.patch("recommendations.openrouter.urllib.request.urlopen")
    def test_errors_become_llm_errors(self, urlopen):
        failures = [
            urllib.error.HTTPError(openrouter.API_URL, 429, "Too Many Requests", {}, io.BytesIO(b"rate limited")),
            urllib.error.URLError("no route"),
            TimeoutError(),
        ]
        for failure in failures:
            urlopen.side_effect = failure
            with self.assertRaises(openrouter.LLMError):
                openrouter.chat_completion([])
        urlopen.side_effect = None
        for body in [b"not json", b'{"error": {"message": "bad key"}}', b'{"choices": []}']:
            urlopen.return_value = FakeResponse(body)
            with self.assertRaises(openrouter.LLMError):
                openrouter.chat_completion([])

    @override_settings(OPENROUTER_API_KEY="")
    def test_missing_key(self):
        with self.assertRaises(openrouter.LLMNotConfigured):
            openrouter.chat_completion([])
