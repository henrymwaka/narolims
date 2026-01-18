"""
Django settings for naro_lims project.

NARO-LIMS
- PostgreSQL
- DRF + JWT
- Cloudflare Tunnel -> Nginx -> Gunicorn (proxy aware)
- Celery + django-celery-beat/results
- Multi-lab configurable packs (workflows, schemas, roles)
"""

from pathlib import Path
from datetime import timedelta
from celery.schedules import crontab
from decouple import config
import os
import sys


# ===============================================================
# Base paths
# ===============================================================
BASE_DIR = Path(__file__).resolve().parent.parent


# ===============================================================
# Security
# ===============================================================
# Never ship an insecure default secret key in production.
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)

_raw_hosts = config(
    "ALLOWED_HOSTS",
    default="narolims.reslab.dev,www.narolims.reslab.dev,127.0.0.1,localhost,testserver,.reslab.dev",
)

ALLOWED_HOSTS = [h.strip() for h in str(_raw_hosts).split(",") if h.strip()]

_fixed_hosts = []
for h in ALLOWED_HOSTS:
    if h.startswith("*."):
        _fixed_hosts.append("." + h[2:])
    else:
        _fixed_hosts.append(h)
ALLOWED_HOSTS = _fixed_hosts

if "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")

LOGIN_URL = "/api/auth/login/"
LOGIN_REDIRECT_URL = "/lims/ui/"
LOGOUT_REDIRECT_URL = "/"

# ---------------------------------------------------------------
# Cloudflare + Nginx + Gunicorn
# ---------------------------------------------------------------
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# HSTS (start low, increase later)
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=3600, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False, cast=bool)
SECURE_HSTS_PRELOAD = config("SECURE_HSTS_PRELOAD", default=False, cast=bool)
# Avoid redirect loops because Cloudflare terminates TLS at the edge
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)

SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=True, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=True, cast=bool)

CSRF_TRUSTED_ORIGINS = [
    "https://narolims.reslab.dev",
    "https://www.narolims.reslab.dev",
]

CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"

# ---------------------------------------------------------------
# Test safety: disable HTTPS redirect + secure cookies during tests
# (prevents 301 -> https://testserver/... in pytest/DRF client)
# ---------------------------------------------------------------
RUNNING_TESTS = (
    "PYTEST_CURRENT_TEST" in os.environ
    or "pytest" in sys.argv
    or "test" in sys.argv
    or os.environ.get("DJANGO_ENV", "").lower() in {"ci", "test"}
)

if RUNNING_TESTS:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0


# ===============================================================
# Installed apps
# ===============================================================
INSTALLED_APPS = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    # Core app
    "lims_core.apps.LimsCoreConfig",
    # Celery
    "django_celery_results",
    "django_celery_beat",
]


# ===============================================================
# Middleware
# ===============================================================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Needs request.user, so keep after AuthenticationMiddleware
    "lims_core.middleware.CurrentUserMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "naro_lims.urls"
WSGI_APPLICATION = "naro_lims.wsgi.application"


# ===============================================================
# Templates
# ===============================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]


# ===============================================================
# Database
# ===============================================================
DJANGO_ENV = os.environ.get("DJANGO_ENV", "").lower()

if DJANGO_ENV in {"ci", "test"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="narolims_db"),
            "USER": config("DB_USER", default="narolims_user"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST", default="127.0.0.1"),
            "PORT": config("DB_PORT", default="5432"),
            "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", default=60, cast=int),
        }
    }


# ===============================================================
# Password validation
# ===============================================================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ===============================================================
# Internationalization
# ===============================================================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Kampala"
USE_I18N = True
USE_TZ = True


# ===============================================================
# Static & media
# ===============================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ===============================================================
# CORS
# ===============================================================
# Keep permissive during early build-out, tighten later.
CORS_ALLOW_ALL_ORIGINS = config("CORS_ALLOW_ALL_ORIGINS", default=True, cast=bool)


# ===============================================================
# Django REST Framework
# ===============================================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "naro_lims.pagination.DefaultPagination",
    "PAGE_SIZE": 50,
}


# ===============================================================
# OpenAPI / Swagger
# ===============================================================
SPECTACULAR_SETTINGS = {
    "TITLE": "NARO-LIMS API",
    "DESCRIPTION": "Modular Laboratory Information Management System for NARO",
    "VERSION": config("API_VERSION", default="0.1.0"),
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "SERVERS": [
        {"url": "https://narolims.reslab.dev", "description": "Production"},
    ],
}


# ===============================================================
# JWT
# ===============================================================
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=config("JWT_ACCESS_MINUTES", default=30, cast=int)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=config("JWT_REFRESH_DAYS", default=1, cast=int)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}


# ===============================================================
# Celery configuration (ISOLATED FROM OMICS)
# ===============================================================
CELERY_BROKER_URL = "redis://127.0.0.1:6379/1"
CELERY_RESULT_BACKEND = "django-db"

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

CELERY_TIMEZONE = "Africa/Kampala"

# Dedicated queue isolation
CELERY_TASK_DEFAULT_QUEUE = "narolims"
CELERY_TASK_DEFAULT_ROUTING_KEY = "narolims"

# Route all tasks from our apps to narolims queue
CELERY_TASK_ROUTES = {
    "lims_core.tasks.*": {"queue": "narolims", "routing_key": "narolims"},
}

CELERY_BEAT_SCHEDULE = {
    "scan-workflow-sla-every-10-mins": {
        "task": "lims_core.tasks.scan_workflow_sla",
        "schedule": crontab(minute="*/10"),
        "args": (),
        "options": {"queue": "narolims", "routing_key": "narolims"},
    }
}


# ===============================================================
# Logging
# ===============================================================
LOG_DIR = config("LOG_DIR", default=str(BASE_DIR / "logs"))
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
        "simple": {"format": "{levelname}: {message}", "style": "{"},
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": os.path.join(LOG_DIR, "django.log"),
            "formatter": "verbose",
        },
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["file", "console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["file"], "level": "WARNING", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO"},
    },
}
