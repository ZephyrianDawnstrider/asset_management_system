#!/bin/sh
set -eu

# Migrations are deliberately excluded from image build and automatic startup.
# Run them only as a separate, explicitly authorized maintenance operation.
exec python -m gunicorn asset_management.wsgi:application \
    --bind "0.0.0.0:${PORT:-10000}" \
    --workers 1 \
    --threads 2 \
    --timeout 60
