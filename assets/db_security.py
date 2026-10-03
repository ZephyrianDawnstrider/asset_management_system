"""Fail closed if a production connection is not isolated to its expected role/schema."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.backends.signals import connection_created
from django.dispatch import receiver


def validate_database_identity(connection):
    if not settings.PRODUCTION:
        return
    expected_role = (settings.ASSET_DB_RUNTIME_ROLE if settings.DJANGO_DB_ROLE == "runtime"
                     else settings.ASSET_DB_MIGRATION_ROLE)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_schema(), current_user, current_setting('search_path')")
            current_schema, current_user, search_path = cursor.fetchone()
    except Exception:
        raise ImproperlyConfigured("The production database session failed its isolation check.") from None
    normalized_path = tuple(part.strip().strip('"') for part in search_path.split(","))
    if (current_schema != settings.ASSET_DB_SCHEMA or current_user != expected_role
            or normalized_path != (settings.ASSET_DB_SCHEMA, "pg_catalog")):
        raise ImproperlyConfigured("The production database session failed its isolation check.")


@receiver(connection_created, dispatch_uid="assets.validate_production_database_identity")
def enforce_database_identity(sender, connection, **kwargs):
    try:
        validate_database_identity(connection)
    except ImproperlyConfigured:
        connection.close()
        raise
