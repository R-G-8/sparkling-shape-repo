# Sprint 1: Walking skeleton

## Sprint goal

Get the whole pipeline working end to end: a Django app with user accounts,
connected to Postgres, deployed to staging, with the A/B test page and a seed
command for grader accounts. No product features yet.

## What shipped

- Django 5.2 app with sign up, log in, log out, and a logged-in dashboard
  placeholder (Django's built-in authentication). <!-- TODO: link PR -->
- Postgres attached via `DATABASE_URL` (Neon), migrations for all schema.
- `python manage.py seed`: creates the admin and member grader accounts,
  passwords from environment variables, safe to run repeatedly. Runs on every
  deploy. <!-- TODO: link PR -->
- A/B test page at `/e1531ff` (SHA-1 of `sparkling-shape`) and
  `/e1531ff/stats`. Variant assigned 50/50 on first visit, kept in the session;
  one impression per visitor, at most one click; counts stored with timestamps.
  <!-- TODO: link PR -->
- `/healthz` health check, logs to stdout, config in environment variables.
- GitHub Actions CI runs the tests against Postgres on every pull request.
- 18 automated tests covering the A/B rules, `/stats`, the seed command, and
  the auth flow.

## What works on staging now

<!-- TODO: staging URL -->
- `/signup`, `/login`, `/dashboard`
- `/e1531ff` and `/e1531ff/stats`
- `/healthz`

## Working with our agents

We gave Claude Code the course requirements file as the spec for the A/B page
and asked it to write tests for each rule (one impression per visitor, sticky
variant, one click, redirect isn't an impression) before deploying. The first
test run failed because Django's hashed static-file storage needs
`collectstatic`, which tests skip; we changed settings to use plain storage in
tests and local development. Lesson: having the agent turn each written rule
into a test caught problems before staging.

## Backlog changes for next sprint

- First user stories written from our user journey (watch-history upload,
  ranking, recommendations, friends). <!-- TODO: link issues -->
- Sprint 2 commitment: CSV upload of Netflix watch history and the first
  ranking screen; set up production.
