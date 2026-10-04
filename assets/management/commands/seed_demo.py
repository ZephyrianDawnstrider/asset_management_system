"""Create a small, repeatable sample inventory in a dedicated demo database."""

import os
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from assets.models import Asset, AssetType, AssignmentHistory, Employee
from asset_management.write_fence import require_writes_unpaused


MARKER_TABLE = 'assets_demo_seed_state'
MARKER_KEY = 'fieldnote-assets-demo-v1'


class Command(BaseCommand):
    help = 'Seed synthetic data into an explicitly selected, empty demo.sqlite3 database.'

    def handle(self, *args, **options):
        require_writes_unpaused()
        alias = 'default'
        configured_path = connections[alias].settings_dict['NAME']
        explicit_path = os.environ.get('ASSET_DB_PATH')
        if not explicit_path:
            raise CommandError('Set ASSET_DB_PATH explicitly to a dedicated demo.sqlite3 file before running this command.')

        expected = Path(explicit_path).expanduser().resolve()
        configured = Path(str(configured_path)).expanduser().resolve()
        if expected != configured or expected.name.casefold() != 'demo.sqlite3':
            raise CommandError('Refusing to seed: ASSET_DB_PATH must match Django’s configured database and end in demo.sqlite3.')
        if connections[alias].vendor != 'sqlite' or not expected.is_file():
            raise CommandError('Refusing to seed: migrate a dedicated SQLite demo.sqlite3 database first.')

        db = connections[alias]
        tables = set(db.introspection.table_names())
        User = get_user_model()
        required_tables = {model._meta.db_table for model in (Employee, AssetType, Asset, AssignmentHistory, User)}
        if not required_tables.issubset(tables):
            raise CommandError('The demo database schema is incomplete. Run migrations against this demo database first.')

        marker_exists = MARKER_TABLE in tables
        if marker_exists:
            with db.cursor() as cursor:
                cursor.execute(f'SELECT version FROM {MARKER_TABLE} WHERE seed_key = %s', [MARKER_KEY])
                marker = cursor.fetchone()
            if not marker or marker[0] != 1:
                raise CommandError('The demo seed marker is missing or unsupported; refusing to change this database.')
        else:
            if any(model.objects.using(alias).exists() for model in (Employee, AssetType, Asset, AssignmentHistory)) or User.objects.using(alias).exists():
                raise CommandError('The database is not empty. The first demo seed only runs on a fresh, dedicated database.')

        with transaction.atomic(using=alias):
            if not marker_exists:
                with db.cursor() as cursor:
                    cursor.execute(
                        f'CREATE TABLE {MARKER_TABLE} '
                        '(seed_key varchar(80) PRIMARY KEY, version integer NOT NULL)'
                    )
                    cursor.execute(
                        f'INSERT INTO {MARKER_TABLE} (seed_key, version) VALUES (%s, %s)',
                        [MARKER_KEY, 1],
                    )
            self._seed(alias)

        self.stdout.write(self.style.SUCCESS('Synthetic demo inventory is ready. Re-running this command will not duplicate its records.'))

    @staticmethod
    def _seed(alias):
        employees = {}
        employee_rows = (
            ('DEMO-001', 'Asha Rao', 'Operations', 'Operations Lead', '2022-02-14'),
            ('DEMO-002', 'Kabir Sen', 'Technology', 'Support Analyst', '2023-06-05'),
            ('DEMO-003', 'Mira Thomas', 'Finance', 'Finance Analyst', '2024-01-08'),
        )
        for employee_id, name, department, designation, start_date in employee_rows:
            employee, _ = Employee.objects.using(alias).get_or_create(
                employee_id=employee_id,
                defaults={
                    'name': name,
                    'department': department,
                    'designation': designation,
                    'start_date': start_date,
                    'is_active': True,
                },
            )
            employees[employee_id] = employee

        types = {}
        type_rows = (
            ('Laptop', 'Serial number', 'Portable computer'),
            ('Monitor', 'Asset tag', 'External display'),
            ('Mobile phone', 'IMEI', 'Company mobile device'),
        )
        for name, identifier_label, description in type_rows:
            asset_type, _ = AssetType.objects.using(alias).get_or_create(
                name=name,
                defaults={
                    'identification_type_label': identifier_label,
                    'object_description': description,
                    'is_active': True,
                },
            )
            types[name] = asset_type

        asset_specs = (
            ('DEMO-LAP-001', 'Fieldnote laptop 01', 'Laptop', employees['DEMO-001']),
            ('DEMO-MON-001', 'Fieldnote display 01', 'Monitor', employees['DEMO-001']),
            ('DEMO-PHN-001', 'Fieldnote phone 01', 'Mobile phone', employees['DEMO-002']),
            ('DEMO-LAP-002', 'Fieldnote laptop 02', 'Laptop', None),
        )
        assets = {}
        for identifier, name, type_name, employee in asset_specs:
            asset, _ = Asset.objects.using(alias).get_or_create(
                unique_identifier=identifier,
                defaults={
                    'asset_type': types[type_name],
                    'asset_name': name,
                    'assigned_to': employee,
                    'disposition': Asset.Disposition.ASSIGNED if employee else Asset.Disposition.READY,
                    'details': 'Synthetic demo record.',
                    'is_active': True,
                },
            )
            if asset.asset_type_id != types[type_name].pk:
                raise CommandError(f'Synthetic identifier {identifier} already belongs to a different asset type.')
            assets[identifier] = asset

        def event(identifier, employee_id, action, date_text):
            occurred_at = datetime.fromisoformat(date_text).replace(tzinfo=datetime_timezone.utc)
            AssignmentHistory.objects.using(alias).get_or_create(
                asset=assets[identifier],
                employee=employees[employee_id],
                action=action,
                occurred_at=occurred_at,
                defaults={'actor': None},
            )

        # Dates and transitions below are synthetic fixtures, not imported history.
        event('DEMO-LAP-001', 'DEMO-003', AssignmentHistory.Action.ASSIGNED, '2025-01-10T09:00:00')
        event('DEMO-LAP-001', 'DEMO-003', AssignmentHistory.Action.RETURNED, '2025-08-12T09:00:00')
        event('DEMO-LAP-001', 'DEMO-001', AssignmentHistory.Action.ASSIGNED, '2025-08-12T09:05:00')
        event('DEMO-MON-001', 'DEMO-001', AssignmentHistory.Action.ASSIGNED, '2025-10-03T09:00:00')
        event('DEMO-PHN-001', 'DEMO-002', AssignmentHistory.Action.ASSIGNED, '2026-01-12T10:30:00')
        event('DEMO-LAP-002', 'DEMO-003', AssignmentHistory.Action.ASSIGNED, '2026-03-02T10:00:00')
        event('DEMO-LAP-002', 'DEMO-003', AssignmentHistory.Action.RETURNED, '2026-04-16T15:45:00')
