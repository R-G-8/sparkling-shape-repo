# Technical notes

## Technical-challenge items

- **CI:** `.github/workflows/ci.yml` runs `manage.py check`, a missing-migration
  check, and the test suite against Postgres on every pull request and push to
  `main`. To finish: require the check in branch protection so failing PRs
  can't merge.
- **Health check:** `/healthz` returns `{"status": "ok"}` when the app and
  database respond, otherwise 503. Render uses it as the service health check.

_More items to be chosen in Sprint 2 (candidates: importing external data from
streaming-service CSVs, structured LLM output for recommendations, a
background job queue for scraping)._

## Testing strategy

- **Unit and integration (Django `TestCase`):** A/B rules (`abtest/tests/`),
  seed command and auth flow (`core/tests/`). These run against a real test
  database (Postgres in CI, SQLite locally).
- **Mocked:** randomness in variant assignment (`choose_variant`), and in
  future the OpenRouter LLM and any scraping or external APIs; tests never call
  real external services.
- **Not tested yet:** visual layout, which we check by hand on staging.
