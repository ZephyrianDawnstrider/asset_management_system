# Fieldnote Assets

Fieldnote Assets is a small Django workspace for an authorized staff member to maintain employee records, register company equipment, track current assignments, and review assignment and return history. Employee overview data can be downloaded as CSV.

## Local setup (Windows PowerShell)

Use a dedicated local database for the demo. The commands below create the schema, add clearly synthetic sample records, and then create a local staff login. They do not use the repository’s historical `db.sqlite3` file.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
New-Item -ItemType Directory -Force data | Out-Null
$env:ASSET_DB_PATH = (Join-Path $PWD 'data\demo.sqlite3')
python manage.py migrate
python manage.py seed_demo
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8761
```

Open `http://127.0.0.1:8761/` and sign in with the staff account created by `createsuperuser`. The application requires staff access to the management screens. The demo command does not create a password or a login account.

`ASSET_DB_PATH` selects the SQLite database used by Django. The setting defaults to `data/assets.sqlite3`; the demo seeder deliberately requires an explicit path whose filename is `demo.sqlite3`. On its first run it checks that the database schema exists and that the employee, asset type, asset, assignment history, and user tables contain no records. It writes a command-owned marker so later runs can safely use `get_or_create` without duplicating the synthetic examples. It does not clear tables or overwrite existing records. Keep this demo database local and separate from any real inventory.

## Main screens

- **Overview:** active employees and coverage by asset category, with CSV export.
- **Employees:** create and update employee records, then open a record to assign or return equipment.
- **Asset register:** browse equipment, current holder, and each asset’s custody timeline.
- **Add an asset:** enter the equipment type, name, identifier, and optional details. New assets begin unassigned.
- **Asset types:** maintain the categories available to the inventory.

To move equipment to another person, return it from the current employee record first, then assign it from the new employee record. This produces explicit history events for both sides of the change. Legacy assignments copied by the migration have no known event date; the interface labels those dates as unavailable.

The CSV export contains one row per active employee and assigned asset, or one row with blank asset fields when an employee has no active assignments. Cells beginning with spreadsheet formula markers are escaped before export.

## Data and migration notes

The default database path is `data/assets.sqlite3`, which is ignored by Git. The checked-in `db.sqlite3` is historical project data; leave it untouched and do not point demo commands at it. Set `ASSET_DB_PATH` explicitly when working with any separate local database.

Migration `0005_assignment_history_global_asset_serial` checks for duplicate asset identifiers before enforcing global uniqueness. If duplicates exist, it stops before changing asset rows and reports only the number of duplicate groups; it does not print identifiers or employee/asset records. Resolve duplicates through a reviewed data migration or a separately reviewed database copy before retrying. Do not delete or edit source rows just to make the migration pass.

## Scope and limitations

This is a local v1 demonstration. SQLite is suitable for a single local operator and is not configured here for concurrent production use, multi-user write load, hosting, backups, monitoring, or operational recovery. Authentication and management screens are staff-gated; there is no employee self-service view or department-scoped access model. The repository’s development settings must be reviewed and replaced with deployment-appropriate secrets, host restrictions, transport security, database, and operational controls before hosting real employee or asset information.

Dependencies are pinned in `requirements.txt` (Django 5.2.17 and django-allauth 65.19.7).
