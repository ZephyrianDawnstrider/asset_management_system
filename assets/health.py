"""Minimal platform health probe without database or configuration details."""

from django.db import DatabaseError, connection
from django.db.migrations.exceptions import MigrationSchemaMissing
from django.db.migrations.executor import MigrationExecutor
from django.core.exceptions import ImproperlyConfigured
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
@never_cache
def health(request):
    try:
        from .db_security import validate_database_identity
        validate_database_identity(connection)
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            return JsonResponse({"status": "unavailable"}, status=503)
    except (DatabaseError, MigrationSchemaMissing, ImproperlyConfigured):
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
