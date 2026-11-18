"""
Seed command: creates the grader accounts and demo data.

Safe to run more than once: accounts are created or updated in place, and the
demo watch history is imported with the same no-duplicates rule as uploads.
Passwords come from environment variables so they never live in git.

    python manage.py seed            # accounts + demo data
    python manage.py seed --no-demo  # accounts only

Demo data: the admin grader gets the sample Netflix history, so there is
something to rank and inspect in /admin straight away. The member grader starts
empty, so graders see the first-run "Choose your service" flow.
"""

import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from library.importers import import_viewing_history, parse_netflix_csv

SAMPLE_HISTORY = Path(settings.BASE_DIR) / "static" / "samples" / "NetflixViewingHistory-sample.csv"

# (role, email env var, default email, password env var, is_admin)
GRADER_ACCOUNTS = [
    ("admin", "GRADER_ADMIN_EMAIL", "admin@example.com", "GRADER_ADMIN_PASSWORD", True),
    ("member", "GRADER_MEMBER_EMAIL", "member@example.com", "GRADER_MEMBER_PASSWORD", False),
]


class Command(BaseCommand):
    help = "Create or update the grader accounts and demo data. Safe to run repeatedly."

    def add_arguments(self, parser):
        parser.add_argument("--no-demo", action="store_true", help="Only create the grader accounts.")

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()

        missing = [pw_var for _, _, _, pw_var, _ in GRADER_ACCOUNTS if not os.environ.get(pw_var)]
        if missing:
            raise CommandError(f"Set these environment variables before seeding: {', '.join(missing)}")

        accounts = {}
        for role, email_var, default_email, pw_var, is_admin in GRADER_ACCOUNTS:
            email = os.environ.get(email_var, default_email)
            # Username is the email, so graders log in with the email address.
            user, created = User.objects.get_or_create(username=email, defaults={"email": email})
            user.email = email
            user.is_staff = is_admin
            user.is_superuser = is_admin
            user.is_active = True
            user.set_password(os.environ[pw_var])
            user.save()
            accounts[role] = user
            self.stdout.write(f"{'Created' if created else 'Updated'} {role} account: {email}")

        if not options["no_demo"]:
            rows = parse_netflix_csv(SAMPLE_HISTORY.read_bytes())
            result = import_viewing_history(accounts["admin"], rows)
            self.stdout.write(
                f"Demo watch history for {accounts['admin'].username}: "
                f"{result.titles_in_file} titles, {result.new_rows} new viewing records."
            )

        self.stdout.write(self.style.SUCCESS("Seed complete."))
