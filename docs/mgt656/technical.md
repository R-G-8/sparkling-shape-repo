# Technical notes

## Technical-challenge items

- **Importing external data (Netflix viewing history):** users upload
  Netflix's `NetflixViewingHistory.csv` (up to 5 MB). We check the whole file
  before saving anything, so a malformed file saves nothing and the error names
  the bad row. We work out the date format (Netflix uses the account's locale),
  group episodes under their show, and save rows to Postgres, not disk. A
  unique constraint makes re-uploads add nothing. Files: `library/importers.py`,
  `library/views.py`, `library/tests/test_import.py`. To see it: log in, choose
  Netflix, and upload the sample file linked on the page.
- **Structured LLM output that drives app behaviour (started):** the
  recommendations page asks OpenRouter for JSON that follows a schema
  (`RESPONSE_SCHEMA`). Before saving, the server checks every item: it drops
  titles already in the user's history and duplicates, cuts reasons to one
  line, and needs at least five usable items. Each user gets a set number of
  LLM calls per day (`RECOMMENDATIONS_DAILY_LIMIT`), and every failure shows a
  friendly message. The API key stays on the server. Files:
  `recommendations/openrouter.py`, `recommendations/services.py`,
  `recommendations/tests/`. To see it: `/recommendations/` with
  `OPENROUTER_API_KEY` set.
- **CI:** `.github/workflows/ci.yml` runs on every pull request and every push
  to `main`. It runs `manage.py check`, checks for missing migrations, and runs
  the test suite against Postgres. To finish: make the check required in
  branch protection so failing PRs can't merge.
- **CD with a deliberate promote step:** merging to `main` deploys staging
  automatically. Production deploys the `production` branch, which moves only
  when someone runs **Actions → Promote to production**
  (`.github/workflows/promote.yml`). The workflow only promotes a commit on
  `main` whose CI passed. It only fast-forwards, so production never runs a
  commit that isn't on `main`. Setup is in the README.
- **Health check:** `/healthz` returns `{"status": "ok"}` when the app and
  database respond, otherwise 503. Render uses it as the health check for both
  services.

_Candidates for Sprint 3: an evaluation set for the recommendation prompt, run
like tests; title details from an external movie API, cached in the database
(#5); end-to-end browser tests in CI._

## Testing strategy

- **Unit (no database):** CSV parsing and show grouping
  (`library/tests/test_import.py`), and parsing and cleaning LLM replies
  (`recommendations/tests/`).
- **Integration (Django `TestCase`, real database: Postgres in CI, SQLite
  locally):** uploads through the view, including re-upload, malformed files,
  size limits and per-user isolation; ranking (Elo updates, pair choice,
  ranked-list order, rejecting picks of other users' titles); recommendations
  end to end with the LLM mocked; A/B rules; seed command; auth flow.
- **Mocked:** OpenRouter. Service tests mock `chat_completion`; client tests
  mock `urllib.request.urlopen` to check the request and every failure mode.
  Variant randomness on the A/B page is mocked too (`choose_variant`). Tests
  never call real external services.
- **In a browser, outside CI:** in Sprint 2 we ran the app the way Render
  does (`DEBUG` off, `build.sh`, gunicorn, Postgres) and clicked through
  every story with a Playwright script at desktop and phone sizes, including
  swipe and arrow-key picks. The script isn't in the repo or CI yet; adding
  it is a Sprint 3 candidate.
- **Not tested:** visual layout, and the real OpenRouter model's answers (they
  vary from run to run; we check the shape of the reply, not the taste of the
  picks).
