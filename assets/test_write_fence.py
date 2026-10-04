"""Schema-0005-compatible write-fence checks."""

import os
import subprocess
import sys

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from .models import Asset, AssetType, Employee


class WriteFenceTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="fence-operator", password="local-test-only", is_staff=True,
        )
        self.employee = Employee.objects.create(
            employee_id="FENCE-01", name="Fence Test", department="Ops",
            designation="Operator", start_date="2026-01-01",
        )
        self.kind = AssetType.objects.create(
            name="Fence Laptop", identification_type_label="Serial",
            object_description="Test fixture",
        )
        self.asset = Asset.objects.create(
            asset_type=self.kind, unique_identifier="FENCE-ASSET", asset_name="Test laptop",
        )

    def test_default_off_allows_normal_staff_post(self):
        self.client.force_login(self.staff)
        with override_settings(ASSET_WRITES_PAUSED=False):
            response = self.client.post(reverse("assign_asset_to_employee"), {
                "employee_id": self.employee.employee_id, "asset_id": self.asset.pk,
            })
        self.assertEqual(response.status_code, 200)
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.assigned_to_id, self.employee.pk)

    def test_paused_rejects_unsafe_methods_before_auth_or_database(self):
        self.client.force_login(self.staff)
        endpoints = (
            reverse("assign_asset_to_employee"),
            reverse("employee_create"),
            reverse("account_login"),
            reverse("account_logout"),
            reverse("admin:index"),
        )
        with override_settings(ASSET_WRITES_PAUSED=True):
            for method in ("post", "put", "patch", "delete"):
                for endpoint in endpoints:
                    with self.subTest(method=method, endpoint=endpoint), self.assertNumQueries(0):
                        response = getattr(self.client, method)(endpoint, data={})
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(response["Cache-Control"], "no-store")
                    self.assertEqual(response["Retry-After"], "120")
            self.assertFalse(Asset.objects.filter(pk=self.asset.pk, assigned_to__isnull=False).exists())

    def test_paused_keeps_public_health_and_staff_reads_but_closes_auth_get(self):
        with override_settings(ASSET_WRITES_PAUSED=True):
            with CaptureQueriesContext(connection) as public_queries:
                self.assertEqual(self.client.get(reverse("home")).status_code, 200)
                self.assertEqual(self.client.get(reverse("health")).status_code, 200)
            self.client.force_login(self.staff)
            with CaptureQueriesContext(connection) as staff_queries:
                self.assertEqual(self.client.get(reverse("employee_list")).status_code, 200)
                self.assertEqual(self.client.get(reverse("asset_list")).status_code, 200)
            for endpoint in (reverse("account_login"), reverse("account_logout"),
                             reverse("admin:index")):
                with self.subTest(endpoint=endpoint), self.assertNumQueries(0):
                    response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 503)
        for query in (*public_queries, *staff_queries):
            self.assertNotIn(query["sql"].lstrip().split()[0].upper(),
                             {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"})

    def test_paused_rejects_all_app_mutating_commands_before_query(self):
        with override_settings(ASSET_WRITES_PAUSED=True):
            for command in ("deactivate_employees", "soft_delete_expired_employees",
                            "populate_employees", "seed_demo"):
                with self.subTest(command=command), self.assertNumQueries(0):
                    with self.assertRaisesMessage(CommandError, "Asset writes are paused"):
                        call_command(command)


class WriteFenceSettingsTests(TestCase):
    def test_strict_default_off_and_explicit_values(self):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for value, expected in ((None, "False"), ("true", "True"), ("off", "False")):
            with self.subTest(value=value):
                env = os.environ.copy()
                env.pop("RENDER", None)
                env["DJANGO_ENV"] = "test"
                env["PYTHONPATH"] = project_root
                if value is None:
                    env.pop("ASSET_WRITES_PAUSED", None)
                else:
                    env["ASSET_WRITES_PAUSED"] = value
                result = subprocess.run(
                    [sys.executable, "-c", "from asset_management.settings import ASSET_WRITES_PAUSED; print(ASSET_WRITES_PAUSED)"],
                    env=env, cwd=project_root, text=True, capture_output=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)
        env["ASSET_WRITES_PAUSED"] = "maybe"
        invalid = subprocess.run(
            [sys.executable, "-c", "from asset_management.settings import ASSET_WRITES_PAUSED"],
            env=env, cwd=project_root, text=True, capture_output=True, timeout=30,
        )
        self.assertNotEqual(invalid.returncode, 0)
        self.assertIn("ASSET_WRITES_PAUSED must be true or false", invalid.stderr)
