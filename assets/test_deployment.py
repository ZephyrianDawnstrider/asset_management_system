import json
import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from asset_management.auth_adapters import OperatorOnlyAccountAdapter, OperatorOnlySocialAccountAdapter
from .models import Asset, AssetType, AssignmentHistory, Employee


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOOD_ENV = {
    "RENDER": "true",
    "DJANGO_SECRET_KEY": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_",
    "DJANGO_ALLOWED_HOSTS": "assets.example.onrender.com",
    "DJANGO_CSRF_TRUSTED_ORIGINS": "https://assets.example.onrender.com",
    "DJANGO_DB_ROLE": "runtime",
    "ASSET_DB_SCHEMA": "assets_portfolio",
    "DATABASE_URL": "postgresql://assets_portfolio_app.psusviqzkhlslmieuotb:placeholder@aws-0-test.pooler.supabase.com:5432/postgres",
}


class ProductionSettingsTests(SimpleTestCase):
    def load_settings(self, overrides, code=None):
        env = os.environ.copy()
        for key in ("RENDER", "DJANGO_ENV", "DJANGO_DEBUG", "DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS",
                    "DJANGO_CSRF_TRUSTED_ORIGINS", "DATABASE_URL", "DJANGO_DB_ROLE", "ASSET_DB_SCHEMA",
                    "ASSET_DB_PATH", "ASSET_BUILD_DB_PATH"):
            env.pop(key, None)
        env.update(GOOD_ENV)
        env.update(overrides)
        env["PYTHONPATH"] = PROJECT_ROOT
        code = code or (
            "import json, asset_management.settings as s; "
            "print(json.dumps({'debug':s.DEBUG,'engine':s.DATABASES['default']['ENGINE'],"
            "'hosts':s.ALLOWED_HOSTS,'csrf':s.CSRF_TRUSTED_ORIGINS,'proxy':s.SECURE_PROXY_SSL_HEADER,"
            "'ssl_redirect':s.SECURE_SSL_REDIRECT,'session_secure':s.SESSION_COOKIE_SECURE,"
            "'csrf_secure':s.CSRF_COOKIE_SECURE,'hsts':s.SECURE_HSTS_SECONDS,"
            "'static':s.STORAGES['staticfiles']['BACKEND'],'db_options':s.DATABASES['default']['OPTIONS']}))"
        )
        return subprocess.run([sys.executable, "-c", code], env=env, cwd=PROJECT_ROOT,
                              text=True, capture_output=True, timeout=45)

    def test_render_forces_secure_production_and_postgres(self):
        result = self.load_settings({})
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = json.loads(result.stdout)
        self.assertFalse(settings["debug"])
        self.assertEqual(settings["engine"], "django.db.backends.postgresql")
        self.assertEqual(settings["proxy"], ["HTTP_X_FORWARDED_PROTO", "https"])
        self.assertTrue(settings["ssl_redirect"])
        self.assertTrue(settings["session_secure"])
        self.assertTrue(settings["csrf_secure"])
        self.assertGreater(settings["hsts"], 0)
        self.assertEqual(settings["static"], "whitenoise.storage.CompressedManifestStaticFilesStorage")
        self.assertEqual(settings["db_options"]["sslmode"], "require")
        self.assertEqual(settings["db_options"]["options"], "-c search_path=assets_portfolio,pg_catalog")

    def test_production_requires_database_secret_hosts_and_csrf(self):
        failures = [
            ({"DATABASE_URL": ""}, "DATABASE_URL is required"),
            ({"DATABASE_URL": "sqlite:///unsafe.sqlite3"}, "Supabase session-pooler"),
            ({"DJANGO_DB_ROLE": ""}, "DJANGO_DB_ROLE"),
            ({"ASSET_DB_SCHEMA": "public"}, "exactly assets_portfolio"),
            ({"DATABASE_URL": "postgresql://other:secret@aws-0-test.pooler.supabase.com:5432/postgres"}, "configured Supabase session-pooler role"),
            ({"DATABASE_URL": "postgresql://assets_portfolio_app.psusviqzkhlslmieuotb:secret@db.psusviqzkhlslmieuotb.supabase.co:5432/postgres"}, "configured Supabase session-pooler role"),
            ({"DJANGO_SECRET_KEY": "short"}, "50 characters"),
            ({"DJANGO_SECRET_KEY": "x" * 64}, "varied characters"),
            ({"DJANGO_DEBUG": "true"}, "must not be enabled"),
            ({"DJANGO_ALLOWED_HOSTS": ""}, "explicit hostnames"),
            ({"DJANGO_ALLOWED_HOSTS": "*"}, "explicit hostnames"),
            ({"DJANGO_CSRF_TRUSTED_ORIGINS": "http://assets.example.onrender.com"}, "https origin"),
            ({"DJANGO_CSRF_TRUSTED_ORIGINS": "https://elsewhere.example"}, "listed in DJANGO_ALLOWED_HOSTS"),
        ]
        for override, message in failures:
            with self.subTest(override=override):
                result = self.load_settings(override)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    def test_invalid_database_error_does_not_echo_credentials(self):
        result = self.load_settings({"DATABASE_URL": "postgresql://user:private-secret@/missing"})
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("private-secret", result.stderr)

    def test_migration_principal_can_be_configured_but_not_used_by_wsgi(self):
        migration_url = "postgresql://assets_portfolio_owner.psusviqzkhlslmieuotb:placeholder@aws-0-test.pooler.supabase.com:5432/postgres"
        result = self.load_settings({"DJANGO_DB_ROLE": "migrator", "DATABASE_URL": migration_url},
                                    "import asset_management.wsgi")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("web process must use DJANGO_DB_ROLE=runtime", result.stderr)
        self.assertNotIn("placeholder", result.stderr)

    def test_build_mode_uses_disposable_sqlite_without_cloud_url(self):
        env = os.environ.copy()
        for key in ("RENDER", "DJANGO_ENV", "DJANGO_DEBUG", "DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS",
                    "DJANGO_CSRF_TRUSTED_ORIGINS", "DATABASE_URL", "DJANGO_DB_ROLE", "ASSET_DB_SCHEMA",
                    "ASSET_DB_PATH", "ASSET_BUILD_DB_PATH"):
            env.pop(key, None)
        env.update({"DJANGO_ENV": "build", "PYTHONPATH": PROJECT_ROOT})
        code = "import json, asset_management.settings as s; print(json.dumps({'debug':s.DEBUG,'engine':s.DATABASES['default']['ENGINE']}))"
        result = subprocess.run([sys.executable, "-c", code], env=env, cwd=PROJECT_ROOT,
                                text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = json.loads(result.stdout)
        self.assertFalse(settings["debug"])
        self.assertEqual(settings["engine"], "django.db.backends.sqlite3")


class DeploymentEndpointTests(TestCase):
    def test_health_is_db_ready_minimal_and_get_only(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(self.client.post(reverse("health")).status_code, 405)
        with patch("assets.health.connection.cursor", side_effect=OperationalError("private db detail")):
            unavailable = self.client.get(reverse("health"))
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(unavailable.json(), {"status": "unavailable"})
        self.assertNotIn(b"private db detail", unavailable.content)
        with patch("assets.health.MigrationExecutor.migration_plan", return_value=[(object(), False)]):
            pending = self.client.get(reverse("health"))
        self.assertEqual(pending.status_code, 503)
        self.assertEqual(pending.json(), {"status": "unavailable"})

    def test_account_adapters_disable_regular_and_social_signup(self):
        self.assertFalse(OperatorOnlyAccountAdapter().is_open_for_signup(None))
        self.assertFalse(OperatorOnlySocialAccountAdapter().is_open_for_signup(None, None))

    def test_signup_endpoint_cannot_create_anonymous_account(self):
        User = get_user_model()
        before = User.objects.count()
        response = Client().post(reverse("account_signup"), {
            "username": "uninvited", "email": "new@example.test",
            "password1": "Valid-Long-Password-8492!", "password2": "Valid-Long-Password-8492!",
        })
        self.assertEqual(User.objects.count(), before)
        self.assertNotEqual(response.status_code, 500)

    def test_health_is_the_only_anonymous_operational_endpoint(self):
        user = get_user_model().objects.create_user(username="anonymous-check", password="valid-test-password")
        employee = Employee.objects.create(employee_id="DEP-1", name="Deployment Check", department="Ops",
                                           start_date="2026-01-01")
        kind = AssetType.objects.create(name="Deployment Laptop", identification_type_label="Serial",
                                        object_description="Synthetic test asset")
        asset = Asset.objects.create(asset_type=kind, unique_identifier="DEP-SERIAL", asset_name="Synthetic")
        routes = [
            reverse("employee_overview"), reverse("employee_overview_csv"), reverse("employee_list"),
            reverse("asset_list"), reverse("employee_detail", args=[employee.employee_id]),
            reverse("asset_history", args=[asset.pk]),
        ]
        for route in routes:
            with self.subTest(route=route):
                self.assertIn(self.client.get(route).status_code, {302, 403})
        response = self.client.post(reverse("assign_asset_to_employee"), {
            "employee_id": employee.employee_id, "asset_id": asset.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(Asset.objects.get(pk=asset.pk).assigned_to)
        self.assertEqual(self.client.get(reverse("account_login")).status_code, 200)
        self.assertIn(self.client.get(reverse("admin:index")).status_code, {302, 403})
        self.assertFalse(AssignmentHistory.objects.exists())

    @patch("assets.db_security.settings")
    def test_database_identity_requires_expected_principal_and_schema(self, configured):
        from .db_security import enforce_database_identity, validate_database_identity

        configured.PRODUCTION = True
        configured.DJANGO_DB_ROLE = "runtime"
        configured.ASSET_DB_SCHEMA = "assets_portfolio"
        configured.ASSET_DB_RUNTIME_ROLE = "assets_portfolio_app"
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ("assets_portfolio", "assets_portfolio_app", "assets_portfolio, pg_catalog")
        validate_database_identity(connection)
        cursor.fetchone.return_value = ("public", "assets_portfolio_app", "assets_portfolio, pg_catalog")
        with self.assertRaises(ImproperlyConfigured):
            validate_database_identity(connection)
        cursor.fetchone.return_value = ("assets_portfolio", "wrong_role", "assets_portfolio, pg_catalog")
        with self.assertRaises(ImproperlyConfigured):
            enforce_database_identity(None, connection)
        connection.close.assert_called_once()
