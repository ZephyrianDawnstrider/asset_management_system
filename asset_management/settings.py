"""Settings for local development and explicitly configured production hosting."""

from pathlib import Path
from urllib.parse import parse_qsl, urlsplit
import os
import re

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _truthy(name):
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


IS_RENDER = _truthy("RENDER")
DJANGO_ENV = os.environ.get("DJANGO_ENV", "").strip().lower()
if DJANGO_ENV and DJANGO_ENV not in {"development", "test", "build", "production"}:
    raise ImproperlyConfigured("DJANGO_ENV must be development, test, build, or production.")
PRODUCTION = IS_RENDER or DJANGO_ENV == "production"
BUILD_MODE = DJANGO_ENV == "build" and not IS_RENDER
SUPABASE_PROJECT_REF = "psusviqzkhlslmieuotb"
ASSET_DB_SCHEMA = "assets_portfolio"
ASSET_DB_RUNTIME_ROLE = "assets_portfolio_app"
ASSET_DB_MIGRATION_ROLE = "assets_portfolio_owner"

_secret = os.environ.get("DJANGO_SECRET_KEY", "")
if PRODUCTION:
    if (len(_secret) < 50 or len(set(_secret)) < 20
            or _secret == "local-development-only-change-before-deploy"):
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY to a random value of at least 50 characters with varied characters.")
    if _truthy("DJANGO_DEBUG"):
        raise ImproperlyConfigured("DJANGO_DEBUG must not be enabled in production.")
    SECRET_KEY = _secret
    DEBUG = False
else:
    SECRET_KEY = _secret or "local-development-only-change-before-deploy"
    DEBUG = False if BUILD_MODE else os.environ.get("DJANGO_DEBUG", "true").strip().lower() in {"1", "true", "yes", "on"}


def _production_hosts():
    raw = os.environ.get("DJANGO_ALLOWED_HOSTS", "").strip()
    hosts = [host.lower() for host in raw.split()]
    valid_host = re.compile(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*\Z")
    if not hosts or any(not valid_host.fullmatch(host) for host in hosts):
        raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS to explicit hostnames separated by spaces.")
    return hosts


if PRODUCTION:
    ALLOWED_HOSTS = _production_hosts()
else:
    ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost 127.0.0.1 testserver").split()

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "assets.apps.AssetsConfig",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
if PRODUCTION or BUILD_MODE:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "asset_management.urls"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
ACCOUNT_ADAPTER = "asset_management.auth_adapters.OperatorOnlyAccountAdapter"
SOCIALACCOUNT_ADAPTER = "asset_management.auth_adapters.OperatorOnlySocialAccountAdapter"
SITE_ID = 1
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

WSGI_APPLICATION = "asset_management.wsgi.application"

if PRODUCTION:
    DJANGO_DB_ROLE = os.environ.get("DJANGO_DB_ROLE", "").strip().lower()
    if DJANGO_DB_ROLE not in {"runtime", "migrator"}:
        raise ImproperlyConfigured("Set DJANGO_DB_ROLE to runtime or migrator explicitly.")
    if os.environ.get("ASSET_DB_SCHEMA", "").strip() != ASSET_DB_SCHEMA:
        raise ImproperlyConfigured("ASSET_DB_SCHEMA must be exactly assets_portfolio.")
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise ImproperlyConfigured("DATABASE_URL is required in production and must point to PostgreSQL.")
    try:
        parsed_database_url = urlsplit(database_url)
        database_host = parsed_database_url.hostname
        database_port = parsed_database_url.port or 5432
    except ValueError:
        raise ImproperlyConfigured("DATABASE_URL must be a valid Supabase session-pooler PostgreSQL URL.") from None
    ssl_params = {}
    for key, value in parse_qsl(parsed_database_url.query, keep_blank_values=True):
        normalized_key = key.lower()
        if normalized_key in {"sslmode", "sslrootcert"}:
            if normalized_key in ssl_params:
                raise ImproperlyConfigured("DATABASE_URL may specify sslmode and sslrootcert only once each.")
            ssl_params[normalized_key] = value
    explicit_sslmode = ssl_params.get("sslmode")
    if explicit_sslmode is not None:
        explicit_sslmode = explicit_sslmode.lower()
        if explicit_sslmode not in {"require", "verify-ca", "verify-full"}:
            raise ImproperlyConfigured(
                "DATABASE_URL sslmode must be require, verify-ca, or verify-full in production."
            )
    sslrootcert = ssl_params.get("sslrootcert")
    if sslrootcert is not None and not sslrootcert:
        raise ImproperlyConfigured("DATABASE_URL sslrootcert must not be empty when provided.")
    system_roots = sslrootcert is not None and sslrootcert.lower() == "system"
    if system_roots and explicit_sslmode in {"require", "verify-ca"}:
        raise ImproperlyConfigured("DATABASE_URL sslrootcert=system requires sslmode=verify-full.")
    required_role = ASSET_DB_RUNTIME_ROLE if DJANGO_DB_ROLE == "runtime" else ASSET_DB_MIGRATION_ROLE
    required_user = f"{required_role}.{SUPABASE_PROJECT_REF}"
    if (parsed_database_url.scheme.lower() not in {"postgres", "postgresql"}
            or not database_host or not database_host.lower().endswith(".pooler.supabase.com")
            or database_port != 5432 or parsed_database_url.path.strip("/") != "postgres"
            or parsed_database_url.username != required_user or not parsed_database_url.password):
        raise ImproperlyConfigured("DATABASE_URL must use the configured Supabase session-pooler role and endpoint.")
    try:
        import dj_database_url
        DATABASES = {"default": dj_database_url.parse(
            database_url, conn_max_age=60, conn_health_checks=True,
        )}
    except Exception:
        # Do not include the URL or parser detail: either may contain credentials.
        raise ImproperlyConfigured("DATABASE_URL could not be parsed as a PostgreSQL connection.") from None
    if DATABASES["default"].get("ENGINE") != "django.db.backends.postgresql":
        raise ImproperlyConfigured("DATABASE_URL must configure the PostgreSQL backend.")
    # libpq18 supports sslrootcert=system and requires verify-full with system roots.
    # Without an explicit CA setting, require preserves the preview's TLS-encrypted
    # connection behavior; callers may request the stronger verify-ca/verify-full modes.
    DATABASES["default"].setdefault("OPTIONS", {}).update({
        "sslmode": explicit_sslmode or ("verify-full" if system_roots else "require"),
        "options": f"-c search_path={ASSET_DB_SCHEMA},pg_catalog",
    })
    if sslrootcert is not None:
        DATABASES["default"]["OPTIONS"]["sslrootcert"] = "system" if system_roots else sslrootcert
    # Database authentication is intentionally split: the WSGI process may only use
    # the restricted app login; explicit `manage.py migrate` uses the schema owner.
else:
    DJANGO_DB_ROLE = "local"
    local_db_name = (Path(os.environ.get("ASSET_DB_PATH", BASE_DIR / "data" / "assets.sqlite3")).expanduser()
                     if not BUILD_MODE else Path(os.getenv("TEMP") or "/tmp") / "asset-management-build.sqlite3")
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": local_db_name,
    }}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles")).expanduser()
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": (
        "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if PRODUCTION or BUILD_MODE else "django.contrib.staticfiles.storage.StaticFilesStorage"
    )},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if PRODUCTION:
    csrf_raw = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").strip()
    CSRF_TRUSTED_ORIGINS = csrf_raw.split()
    if not CSRF_TRUSTED_ORIGINS:
        raise ImproperlyConfigured("Set DJANGO_CSRF_TRUSTED_ORIGINS to explicit https:// origins.")
    for origin in CSRF_TRUSTED_ORIGINS:
        try:
            parsed_origin = urlsplit(origin)
            origin_host = parsed_origin.hostname
        except ValueError:
            raise ImproperlyConfigured("Every CSRF trusted origin must be an https origin listed in DJANGO_ALLOWED_HOSTS.") from None
        if (parsed_origin.scheme != "https" or not origin_host or parsed_origin.username or parsed_origin.password or parsed_origin.path
                or parsed_origin.query or parsed_origin.fragment or parsed_origin.hostname not in ALLOWED_HOSTS):
            raise ImproperlyConfigured("Every CSRF trusted origin must be an https origin listed in DJANGO_ALLOWED_HOSTS.")

    # Render terminates TLS at its trusted edge and sets X-Forwarded-Proto.
    if IS_RENDER:
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
