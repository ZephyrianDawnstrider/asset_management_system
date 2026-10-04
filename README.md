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

## UI refinement — 2026-10-03 (v2)

The employee directory and asset register support server-side search, filters, result counts, and pagination. The overview has the same employee filters and pages while its summary cards remain global totals. Employee and asset custody histories are available as complete, paginated timelines (20 events per page). The CSV action exports all active employees; it does not follow the current overview filters or page.

At narrow screen widths, the current operator and sign-out action remain in the navigation, filter controls stack, tables scroll within their own region, and keyboard focus stays visible. Assignment and return actions show a saving status, prevent duplicate submissions, and restore the action after a failed request. These details do not change the staff-only access model or the separate return-then-assign workflow.

An employee exit date is their final active day. Automatic offboarding runs after that date, when `exit_date` is before today. The explicit Deactivate action in the employee directory remains immediate and returns their assigned assets through the recorded workflow.

This remains a local v1 demonstration with a v2 UI refinement: server-side pagination and clearer custody history do not make SQLite suitable for concurrent production writes or add hosting, backups, monitoring, operational recovery, employee self-service, or department-scoped access.

## Render packaging readiness — 2026-10-03

An additive, free-only Docker/Blueprint packaging draft is available in [`docs/render-free-preview.md`](docs/render-free-preview.md). It is not a deployed service and does not provision storage. `render.yaml` is an image-backed manual template with a placeholder image URL, auto-deploy disabled, and externally supplied PostgreSQL configuration; no database resource is declared. Build runs static collection only, and ordinary startup does not migrate or seed data. The tracked historical database is excluded from the Docker context and image, but remains in the repository history; do not use a Git-based external build route.

The approved target is the existing private Supabase `assets_portfolio` schema; the authorized operator still needs to confirm credentials and isolation. No new database is provisioned by this work. Render Free PostgreSQL expires after 30 days, is limited to 1 GB, and has no backups, so it is not a durable fallback. Restart persistence, backup/recovery, image review, and hosted acceptance remain pending. Do not connect or deploy this configuration with real data until those gates are resolved.

## Portfolio case study — 2026-10-04 (supersedes earlier demo and packaging status)

**Problem.** Equipment can be registered while the handoff between people gets lost. Fieldnote Assets gives staff one place to see current custody and the sequence of changes behind it. The earlier local-only and packaging sections above remain historical snapshots; verify the live release separately from this source tree.

**Walkthrough.** The [public demo](https://asset-management-portfolio.onrender.com/) opens with a clearly synthetic, read-only example: search for an asset, inspect its holder and custody event, then return it before reassignment. Actual records require staff sign-in. A staff member registers an asset, assigns it from an employee record, returns it before transfer, and reviews the asset or employee timeline. The overview surfaces available active assets and recent custody events. The register exports all rows matching its current search, category, and status filters, regardless of pagination; the separate employee export still covers all active employees.

**Implementation.** Django views and templates use the existing Employee, Asset, AssetType, and AssignmentHistory models. Server-side query filters and pagination keep staff lists bounded; the asset CSV reuses the register filter rules and escapes spreadsheet formula prefixes. Assignment services enforce current-holder checks and write history events. This update needs no schema migration.

**Access and audit.** Management views and both CSV endpoints require staff access. The public walkthrough uses static synthetic content and no live inventory query. Custody timelines remain readable to staff after asset retirement or employee deactivation; older migrated events can have an unavailable date. The operator and event time appear where recorded.

**Tradeoffs and limits.** Availability is not a maintenance or overdue signal: there is no due date, warranty, or maintenance model. Transfer remains an explicit return followed by a new assignment. This is an operator workspace, without employee self-service or department-scoped authorization. The public demo does not supply a guest staff account. Verify release, hosted flows, and backup/recovery gates against their current receipts before claiming production readiness. Focused tests cover staff access, the synthetic public page, operations data, filtered CSV, and formula escaping.

## Offboarding and asset recovery — 2026-10-04 (source milestone)

The staff overview now highlights active employees who still hold active assets when their recorded final active day has passed or falls within the next 14 days. It shows the earliest eight records and the total requiring review. A final active day is **not** an asset return due date; the data model has no return deadline, so this queue is a custody review aid rather than an overdue claim.

Employee records now show an offboarding checklist with the final active day, current active asset count, individual return controls, and the existing immediate deactivation action. Deactivation returns remaining active assets within the existing transaction and keeps assignment history. Inactive employee detail pages are read-only, and direct edit/delete routes reject inactive records while their history remains available. This milestone adds no model or migration and does not reactivate employees, add maintenance tracking, or change the staff-only access boundary. Verify the deployed revision separately from this source description.

## Interactive public walkthrough — 2026-10-04 (source stage 1)

The public landing page now presents a clearly labeled synthetic, in-page custody scenario. Visitors can search and select sample assets, try a guarded return-before-reassignment flow, watch synthetic timeline and offboarding guidance update, and reset the scenario. The demo keeps state only in page memory; it makes no API call, saves nothing locally, and never reads or changes staff inventory. Public navigation links point to the demo, workflow explanation, and access note. Actual records and operations remain behind staff sign-in. This source stage is separate from the live deployment and does not change models, migrations, or assignment services.

## Condition-aware custody and recovery — 2026-10-04 (source stage 2; supersedes offboarding return behavior above)

An active asset has one explicit disposition: ready, assigned, recovery pending, reported missing, or inspection hold. Assignment requires ready disposition. Deactivating an employee leaves each unreceived asset linked to that employee, opens one auditable recovery case, and adds a recovery event. It does not claim the asset was physically returned. Staff can report a held asset missing or record physical receipt as usable or damaged. A usable receipt clears the holder and makes the asset ready; a damaged receipt clears the holder but keeps the asset on inspection hold until staff records an inspection resolution. The employee and asset timelines retain case identity, actor, recorded time, optional observed time, reason, and resolution. Legacy return events are labeled as physically unverified. Staff-only access remains in effect, including recovery controls on inactive employee records. The register, API, overview, and CSV use these dispositions consistently.

Migrations `0006`–`0008` add the case and event fields, backfill held active assets, and enforce custody constraints. A preflight stops before schema changes if a retired asset still has a holder; those historical rows need a separately reviewed, audited resolution. The data backfill is forward-only: reversing its code cannot reconstruct earlier custody states or remove generated evidence safely. A production rollback requires a verified backup restore or an explicitly reviewed forward correction. The new case table and identity sequence have private runtime-role grant SQL in the migration, but production owner, role, grant, and sequence identities must be verified before applying it. This source stage does not assert that the production database, Render service, or hosted flow has been updated.

Production application is a coupled database and code cutover. The old deployed code writes `assigned_to` without disposition and will conflict with the new constraint, while the new code needs the added fields. Before applying the migration, the operators need a coordinated maintenance or write-quiesce window, verified backup, migration ledger and grant checks, exact release SHA, and a tested restore or forward-correction plan. Resume writes only after the matching code is deployed and its hosted flows are verified.

Maintenance dispatch and return are not modeled. Inspection hold is the current boundary after a damaged receipt; staff can document inspection resolution and then make the asset ready. The public walkthrough remains synthetic and may need a separate update to demonstrate these new staff flows.

## Live custody caveat — 2026-10-04 18:10 IST (supersedes any live-feature inference above)

At the last verified Render snapshot, the live sanitized revision was `bf2b9ba824e967be0f679c5836ea6a2ebddca81f`. Its `deactivate_employee()` calls `return_employee_assets()`, which clears an asset's holder and records `RETURNED` without a physical receipt. Treat those historical return events as physically unverified; they do not prove that staff recovered an item. Recheck the exact Render deploy and commit before describing current behavior, because a later deployment may supersede this snapshot.

Stage 2 custody and recovery behavior in this source tree is **not a live feature claim**. Its production release requires the reviewed write fence, old-instance drain, database writer denial, verified backup and restore rehearsal, migrations `0006`–`0008`, a matching sanitized deploy, and hosted staff acceptance. Acceptance must show that deactivation retains each unreceived holder and opens a recovery case without a `RETURNED` event; only an explicit physical receipt clears custody. Old application instances and external writers must be unable to write across the schema cutover. Until those gates are evidenced, the public demo and hosted staff workflow should be described as the exact deployed Stage 1 revision, with this custody limitation.
