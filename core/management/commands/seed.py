"""
Seed command: creates the grader accounts (and later, demo data).

Safe to run more than once: accounts are created or updated in place, never
duplicated. Passwords come from environment variables so they never live in git.

    python manage.py seed
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# (role, email env var, default email, password env var, is_admin)
GRADER_ACCOUNTS = [
    ("admin", "GRADER_ADMIN_EMAIL", "admin@example.com", "GRADER_ADMIN_PASSWORD", True),
    ("member", "GRADER_MEMBER_EMAIL", "member@example.com", "GRADER_MEMBER_PASSWORD", False),
]


class Command(BaseCommand):
    help = "Create or update the grader accounts and demo data. Safe to run repeatedly."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()

        missing = [pw_var for _, _, _, pw_var, _ in GRADER_ACCOUNTS if not os.environ.get(pw_var)]
        if missing:
            raise CommandError(f"Set these environment variables before seeding: {', '.join(missing)}")

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
            self.stdout.write(f"{'Created' if created else 'Updated'} {role} account: {email}")

        self.stdout.write(self.style.SUCCESS("Seed complete."))
