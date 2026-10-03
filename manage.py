#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    production = (os.environ.get('RENDER', '').strip().lower() in {'1', 'true', 'yes', 'on'}
                  or os.environ.get('DJANGO_ENV', '').strip().lower() == 'production')
    if production and len(sys.argv) > 1 and sys.argv[1] == 'migrate':
        if os.environ.get('DJANGO_DB_ROLE', '').strip().lower() != 'migrator':
            raise SystemExit('Production migrations require DJANGO_DB_ROLE=migrator and the separate schema-owner DATABASE_URL.')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'asset_management.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
