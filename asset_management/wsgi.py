"""
WSGI config for asset_management project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'asset_management.settings')

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.wsgi import get_wsgi_application

if settings.PRODUCTION and settings.DJANGO_DB_ROLE != 'runtime':
    raise ImproperlyConfigured('The web process must use DJANGO_DB_ROLE=runtime and the restricted app database login.')

application = get_wsgi_application()
