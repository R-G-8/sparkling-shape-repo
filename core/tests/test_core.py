from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.urls import reverse

GRADER_ENV = {
    "GRADER_ADMIN_PASSWORD": "test-admin-pw-123",
    "GRADER_MEMBER_PASSWORD": "test-member-pw-456",
}


class SeedCommandTests(TestCase):
    @mock.patch.dict("os.environ", GRADER_ENV)
    def test_creates_grader_accounts(self):
        call_command("seed", stdout=mock.MagicMock())
        User = get_user_model()
        admin = User.objects.get(username="admin@example.com")
        member = User.objects.get(username="member@example.com")
        self.assertTrue(admin.is_superuser and admin.is_staff)
        self.assertFalse(member.is_superuser or member.is_staff)
        self.assertTrue(admin.check_password("test-admin-pw-123"))
        self.assertTrue(member.check_password("test-member-pw-456"))

    @mock.patch.dict("os.environ", GRADER_ENV)
    def test_safe_to_run_twice(self):
        call_command("seed", stdout=mock.MagicMock())
        call_command("seed", stdout=mock.MagicMock())
        self.assertEqual(get_user_model().objects.count(), 2)

    @mock.patch.dict("os.environ", {}, clear=True)
    def test_requires_passwords(self):
        with self.assertRaises(CommandError):
            call_command("seed", stdout=mock.MagicMock())

    @mock.patch.dict("os.environ", GRADER_ENV)
    def test_grader_can_log_in(self):
        call_command("seed", stdout=mock.MagicMock())
        response = self.client.post(
            reverse("login"),
            {"username": "member@example.com", "password": "test-member-pw-456"},
        )
        self.assertRedirects(response, reverse("dashboard"))


class AuthFlowTests(TestCase):
    def test_public_pages(self):
        for name in ("home", "login", "signup"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_signup_logs_in(self):
        response = self.client.post(
            reverse("signup"),
            {"username": "newuser", "password1": "a-long-unique-pw-9", "password2": "a-long-unique-pw-9"},
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(get_user_model().objects.filter(username="newuser").exists())

    def test_healthz(self):
        self.assertEqual(self.client.get(reverse("healthz")).json(), {"status": "ok"})
