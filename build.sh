#!/bin/sh
set -eu

# Build-only settings use a disposable SQLite path and never contact production.
export DJANGO_ENV=build
export DJANGO_SECRET_KEY='build-only-not-a-runtime-secret'
export ASSET_BUILD_DB_PATH=/tmp/asset-management-build.sqlite3

python manage.py collectstatic --noinput
