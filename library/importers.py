"""
Import a Netflix viewing-activity CSV (NetflixViewingHistory.csv).

Netflix's file has two columns, Title and Date, one row per episode or film:

    Title,Date
    "Squid Game: Season 1: Red Light, Green Light",9/17/21
    The Irishman,11/29/19

The whole file is parsed and checked before anything is written, so a malformed
file saves nothing. Rows are written to the database (never to disk), and the
unique constraint on ViewingActivity makes re-uploading the same file a no-op.
"""

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.db import transaction

from .models import RankedTitle, Title, ViewingActivity

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_TITLE_LENGTH = 500

# Netflix writes dates in the account's locale. Try US order first (Netflix's
# default), then day-first and ISO. A file uses one format throughout, so we pick
# the first format that parses every row without producing a future date.
DATE_FORMATS = [
    "%m/%d/%y",
    "%m/%d/%Y",
    "%d/%m/%y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d.%m.%y",
    "%d.%m.%Y",
    "%d-%m-%Y",
    "%d-%m-%y",
]

# "Show: Season 1: Episode name" -> "Show". The season marker must be followed by
# another segment (the episode name), so films such as "Kill Bill: Vol. 1" keep
# their full name.
_SEASON_MARKER = (
    r"(?:Season|Series|Limited Series|Miniseries|Mini-Series|Part|Volume|Vol\.|Book|"
    r"Chapter|Collection|Temporada|Staffel|Saison)"
)
_EPISODE_RE = re.compile(rf"^(?P<show>.+?):\s+{_SEASON_MARKER}\b[^:]*:\s*\S", re.IGNORECASE)
_BARE_EPISODE_RE = re.compile(r"^(?P<show>.+?):\s+(?:Episode|Ep\.?)\s*\d+\s*$", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


class CSVImportError(Exception):
    """The file can't be imported. The message is shown to the user as-is."""


@dataclass(frozen=True)
class ImportResult:
    rows_in_file: int
    new_rows: int
    titles_in_file: int
    new_titles: int

    @property
    def duplicate_rows(self):
        return self.rows_in_file - self.new_rows


def clean_title(raw):
    return _WHITESPACE_RE.sub(" ", raw).strip()


def show_name(raw_title):
    """The show (or film) a Netflix title belongs to."""
    title = clean_title(raw_title)
    for pattern in (_EPISODE_RE, _BARE_EPISODE_RE):
        match = pattern.match(title)
        if match:
            show = match.group("show").strip()
            # "Stranger Things: Stranger Things 4: Chapter One" -> "Stranger Things"
            head, sep, rest = show.partition(": ")
            if sep and rest.casefold().startswith(head.casefold()):
                return head
            return show
    return title


def _decode(data):
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise CSVImportError(
        "We couldn't read this file as text. Upload the CSV exactly as Netflix downloaded it."
    )


def _pick_date_format(raw_dates, today):
    latest_allowed = today + timedelta(days=1)
    for fmt in DATE_FORMATS:
        try:
            parsed = [datetime.strptime(value, fmt).date() for value in raw_dates]
        except ValueError:
            continue
        if all(d <= latest_allowed for d in parsed):
            return fmt, parsed
    return None, None


def parse_netflix_csv(data, today=None):
    """Parse the bytes of a Netflix viewing-activity CSV.

    Returns a list of (raw_title, watched_on) tuples, or raises CSVImportError
    with a message that tells the user what is wrong.
    """
    if not data.strip():
        raise CSVImportError("This file is empty.")

    text = _decode(data)
    try:
        rows = list(csv.reader(io.StringIO(text, newline="")))
    except csv.Error as exc:
        raise CSVImportError(f"This doesn't look like a CSV file ({exc}).") from exc

    # Drop blank lines (Excel sometimes adds them at the end).
    numbered = [(number, row) for number, row in enumerate(rows, start=1) if any(cell.strip() for cell in row)]
    if not numbered:
        raise CSVImportError("This file is empty.")

    header_number, header = numbered[0]
    columns = [cell.strip().lower() for cell in header]
    if "title" not in columns or "date" not in columns:
        raise CSVImportError(
            "This doesn't look like a Netflix viewing-activity file: the first row should be "
            "the column names Title and Date."
        )
    title_col, date_col = columns.index("title"), columns.index("date")

    body = numbered[1:]
    if not body:
        raise CSVImportError("This file has column names but no titles in it.")

    titles, raw_dates = [], []
    for number, row in body:
        if len(row) <= max(title_col, date_col):
            raise CSVImportError(f"Row {number} is missing its title or date.")
        title, raw_date = clean_title(row[title_col]), row[date_col].strip()
        if not title:
            raise CSVImportError(f"Row {number} has no title.")
        if not raw_date:
            raise CSVImportError(f'Row {number} ("{title[:60]}") has no date.')
        if len(title) > MAX_TITLE_LENGTH:
            raise CSVImportError(f"Row {number} has a title longer than {MAX_TITLE_LENGTH} characters.")
        titles.append(title)
        raw_dates.append(raw_date)

    fmt, dates = _pick_date_format(raw_dates, today or date.today())
    if fmt is None:
        # Point at the first row whose date no format can read.
        for (number, _), raw_date in zip(body, raw_dates):
            if not any(_parses(raw_date, f) for f in DATE_FORMATS):
                raise CSVImportError(f'Row {number} has a date we can\'t read: "{raw_date[:30]}".')
        raise CSVImportError(
            "The dates in this file aren't in one consistent format. Upload the file exactly as "
            "Netflix downloaded it."
        )

    return list(zip(titles, dates))


def _parses(value, fmt):
    try:
        datetime.strptime(value, fmt)
        return True
    except ValueError:
        return False


def _chunks(items, size=500):
    items = list(items)
    for start in range(0, len(items), size):
        yield items[start : start + size]


@transaction.atomic
def import_viewing_history(user, rows, service=ViewingActivity.NETFLIX):
    """Save parsed rows for `user`. Safe to repeat: existing rows are skipped."""
    names_by_raw = {raw: show_name(raw) for raw, _ in rows}
    names = set(names_by_raw.values())

    Title.objects.bulk_create([Title(name=name) for name in names], ignore_conflicts=True, batch_size=1000)
    title_ids = {}
    for chunk in _chunks(names):
        title_ids.update(Title.objects.filter(name__in=chunk).values_list("name", "id"))

    activity = ViewingActivity.objects.filter(user=user)
    before = activity.count()
    ViewingActivity.objects.bulk_create(
        [
            ViewingActivity(
                user=user, title_id=title_ids[names_by_raw[raw]], raw_title=raw, watched_on=watched_on, service=service
            )
            for raw, watched_on in rows
        ],
        ignore_conflicts=True,
        batch_size=1000,
    )
    new_rows = activity.count() - before

    ranked = RankedTitle.objects.filter(user=user)
    ranked_before = ranked.count()
    RankedTitle.objects.bulk_create(
        [RankedTitle(user=user, title_id=title_id) for title_id in set(title_ids.values())],
        ignore_conflicts=True,
        batch_size=1000,
    )

    return ImportResult(
        rows_in_file=len(rows),
        new_rows=new_rows,
        titles_in_file=len(names),
        new_titles=ranked.count() - ranked_before,
    )
