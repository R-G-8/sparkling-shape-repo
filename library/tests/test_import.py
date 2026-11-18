from datetime import date
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from library.importers import CSVImportError, parse_netflix_csv, show_name
from library.models import RankedTitle, Title, ViewingActivity

SAMPLE = Path(settings.BASE_DIR) / "static" / "samples" / "NetflixViewingHistory-sample.csv"

GOOD_CSV = (
    b"Title,Date\n"
    b'"Squid Game: Season 1: Red Light, Green Light",9/17/21\n'
    b'"Squid Game: Season 1: Hell",9/18/21\n'
    b"The Irishman,11/29/19\n"
)


def upload(content, name="NetflixViewingHistory.csv"):
    return SimpleUploadedFile(name, content, content_type="text/csv")


class ShowNameTests(SimpleTestCase):
    def test_episodes_group_under_their_show(self):
        cases = {
            "Squid Game: Season 1: Red Light, Green Light": "Squid Game",
            "The Queen's Gambit: Limited Series: Openings": "The Queen's Gambit",
            "Money Heist: Part 1: Episode 1": "Money Heist",
            "Arcane: League of Legends: Season 1: Welcome to the Playground": "Arcane: League of Legends",
            "Stranger Things: Stranger Things 4: Chapter One: The Hellfire Club": "Stranger Things",
            "Lupin: Part 1: Chapter 1": "Lupin",
            "Some Docuseries: Episode 3": "Some Docuseries",
        }
        for raw, expected in cases.items():
            self.assertEqual(show_name(raw), expected, raw)

    def test_films_keep_their_full_name(self):
        for film in ["The Irishman", "Kill Bill: Vol. 1", "Dune: Part Two", "Glass Onion: A Knives Out Mystery"]:
            self.assertEqual(show_name(film), film)

    def test_whitespace_is_tidied(self):
        self.assertEqual(show_name("  The   Irishman "), "The Irishman")


class ParseTests(SimpleTestCase):
    def test_parses_netflix_format(self):
        rows = parse_netflix_csv(GOOD_CSV)
        self.assertEqual(
            rows,
            [
                ("Squid Game: Season 1: Red Light, Green Light", date(2021, 9, 17)),
                ("Squid Game: Season 1: Hell", date(2021, 9, 18)),
                ("The Irishman", date(2019, 11, 29)),
            ],
        )

    def test_handles_byte_order_mark_crlf_and_blank_lines(self):
        rows = parse_netflix_csv(b"\xef\xbb\xbfTitle,Date\r\nRoma,12/14/18\r\n\r\n")
        self.assertEqual(rows, [("Roma", date(2018, 12, 14))])

    def test_day_first_dates(self):
        # 25/12 can only be day-first, so the whole file is read that way.
        rows = parse_netflix_csv(b"Title,Date\nRoma,25/12/2020\nDark,03/01/2021\n")
        self.assertEqual([d for _, d in rows], [date(2020, 12, 25), date(2021, 1, 3)])

    def test_iso_dates_and_column_order(self):
        rows = parse_netflix_csv(b"date,title\n2024-02-01,Roma\n")
        self.assertEqual(rows, [("Roma", date(2024, 2, 1))])

    def test_sample_file_parses(self):
        rows = parse_netflix_csv(SAMPLE.read_bytes())
        self.assertGreater(len(rows), 40)

    def test_malformed_files_give_clear_errors(self):
        cases = {
            b"": "empty",
            b"\n\n": "empty",
            b"Name,When\nRoma,1/2/20\n": "Title and Date",
            b"Title,Date\n": "no titles",
            b"Title,Date\nRoma,1/2/20\n,1/3/20\n": "Row 3 has no title",
            b"Title,Date\nRoma,\n": "Row 2",
            b"Title,Date\nRoma,1/2/20\nDark,yesterday\n": 'Row 3 has a date we can\'t read: "yesterday"',
            b"Title,Date\nRoma\n": "Row 2 is missing",
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR": "",
        }
        for content, expected in cases.items():
            with self.subTest(content=content[:20]):
                with self.assertRaises(CSVImportError) as ctx:
                    parse_netflix_csv(content)
                self.assertIn(expected, str(ctx.exception))

    def test_ambiguous_dates_default_to_month_first(self):
        rows = parse_netflix_csv(b"Title,Date\nRoma,12/01/99\n", today=date(2026, 11, 18))
        self.assertEqual(rows[0][1], date(1999, 12, 1))

    def test_future_dates_rule_out_a_format(self):
        # Month-first, 12/11/26 would be 11 Dec 2026, after "today", so it must be day-first.
        rows = parse_netflix_csv(b"Title,Date\nRoma,12/11/26\n", today=date(2026, 11, 18))
        self.assertEqual(rows[0][1], date(2026, 11, 12))


class UploadViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("viewer", password="a-long-unique-pw-9")
        self.client.force_login(self.user)
        self.url = reverse("service_import", args=["netflix"])

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('login')}?next={self.url}")

    def test_netflix_page_has_steps_link_and_upload_form(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn('href="https://www.netflix.com/viewingactivity"', html)
        self.assertIn("Download all", html)
        self.assertIn('type="file"', html)
        self.assertIn('enctype="multipart/form-data"', html)

    def test_upload_saves_each_row_for_this_user_and_reports_counts(self):
        response = self.client.post(self.url, {"file": upload(GOOD_CSV)}, follow=True)
        self.assertRedirects(response, reverse("dashboard"))
        self.assertContains(response, "Imported 2 titles from 3 viewing records: 3 new.")
        rows = ViewingActivity.objects.filter(user=self.user)
        self.assertEqual(rows.count(), 3)
        self.assertEqual(
            set(rows.values_list("raw_title", "watched_on")),
            {
                ("Squid Game: Season 1: Red Light, Green Light", date(2021, 9, 17)),
                ("Squid Game: Season 1: Hell", date(2021, 9, 18)),
                ("The Irishman", date(2019, 11, 29)),
            },
        )
        self.assertEqual(
            set(RankedTitle.objects.filter(user=self.user).values_list("title__name", flat=True)),
            {"Squid Game", "The Irishman"},
        )

    def test_reupload_creates_no_duplicates(self):
        self.client.post(self.url, {"file": upload(GOOD_CSV)})
        response = self.client.post(self.url, {"file": upload(GOOD_CSV)}, follow=True)
        self.assertContains(response, "already in your history, so nothing was added")
        self.assertEqual(ViewingActivity.objects.count(), 3)
        self.assertEqual(RankedTitle.objects.count(), 2)
        self.assertEqual(Title.objects.count(), 2)

    def test_partial_overlap_counts_only_new_rows(self):
        self.client.post(self.url, {"file": upload(GOOD_CSV)})
        response = self.client.post(self.url, {"file": upload(GOOD_CSV + b"Roma,12/14/18\n")}, follow=True)
        self.assertContains(response, "Imported 3 titles from 4 viewing records: 1 new, 3 already in your history.")
        self.assertEqual(ViewingActivity.objects.count(), 4)

    def test_malformed_file_shows_error_and_saves_nothing(self):
        bad = GOOD_CSV + b"Dark,not-a-date\n"
        response = self.client.post(self.url, {"file": upload(bad)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Row 5 has a date we can&#x27;t read")
        self.assertEqual(ViewingActivity.objects.count(), 0)
        self.assertEqual(Title.objects.count(), 0)
        self.assertEqual(RankedTitle.objects.count(), 0)

    def test_rejects_non_csv(self):
        response = self.client.post(self.url, {"file": upload(GOOD_CSV, name="history.xlsx")})
        self.assertContains(response, "Choose a .csv file")
        self.assertEqual(ViewingActivity.objects.count(), 0)

    def test_rejects_files_over_5_mb(self):
        big = GOOD_CSV + b"x" * (5 * 1024 * 1024)
        response = self.client.post(self.url, {"file": upload(big)})
        self.assertContains(response, "larger than 5 MB")
        self.assertEqual(ViewingActivity.objects.count(), 0)

    def test_accepts_a_file_just_under_5_mb(self):
        line = b"A Very Long Documentary Title That Pads The File Out Nicely,1/2/20\n"
        body = b"Title,Date\n" + line * ((5 * 1024 * 1024 - 100) // len(line))
        self.assertLess(len(body), 5 * 1024 * 1024)
        response = self.client.post(self.url, {"file": upload(body)}, follow=True)
        self.assertContains(response, "Imported 1 title from")
        self.assertEqual(ViewingActivity.objects.count(), 1)

    def test_rows_belong_to_the_uploader_only(self):
        other = get_user_model().objects.create_user("other", password="a-long-unique-pw-9")
        self.client.post(self.url, {"file": upload(GOOD_CSV)})
        self.assertEqual(ViewingActivity.objects.filter(user=other).count(), 0)
        self.client.force_login(other)
        self.client.post(self.url, {"file": upload(GOOD_CSV)})
        self.assertEqual(ViewingActivity.objects.filter(user=other).count(), 3)
        self.assertEqual(Title.objects.count(), 2)  # titles are shared

    def test_upload_is_not_written_to_disk(self):
        # Valid uploads (5 MB max) stay in memory rather than a temporary file.
        self.assertGreaterEqual(settings.FILE_UPLOAD_MAX_MEMORY_SIZE, 5 * 1024 * 1024 + 64 * 1024)


class ServicePickerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("viewer", password="a-long-unique-pw-9")
        self.client.force_login(self.user)

    def test_first_dashboard_shows_choose_your_service(self):
        html = self.client.get(reverse("dashboard")).content.decode()
        self.assertIn("Choose your service", html)
        self.assertIn(reverse("service_import", args=["netflix"]), html)

    def test_dashboard_moves_on_after_import(self):
        self.client.post(reverse("service_import", args=["netflix"]), {"file": upload(GOOD_CSV)})
        html = self.client.get(reverse("dashboard")).content.decode()
        self.assertNotIn("Choose your service", html)
        self.assertIn("Start ranking", html)

    def test_other_services_are_coming_soon(self):
        response = self.client.get(reverse("service_import", args=["disney-plus"]))
        self.assertContains(response, "coming soon")
        self.assertNotContains(response, 'type="file"')

    def test_unknown_service_404s(self):
        self.assertEqual(self.client.get(reverse("service_import", args=["nope"])).status_code, 404)

    def test_choose_service_page(self):
        response = self.client.get(reverse("choose_service"))
        self.assertContains(response, "Netflix")
        self.assertContains(response, "coming soon")
