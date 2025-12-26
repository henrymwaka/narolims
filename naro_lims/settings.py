"""
Django settings for naro_lims project.
Adapted for NARO-LIMS with PostgreSQL, JWT, Cloudflare, DRF,
workflow enforcement, audit safety, and Celery background tasks.
"""

from pathlib import Path
from decouple import config
from datetime import timedelta
from celery.schedules import crontab
import os


# ===============================================================
# Base paths
# ===============================================================
BASE_DIR = Path(__file__).resolve().parent.parent


# ===============================================================
# Security
# ===============================================================
SECRET_KEY = config("SECRET_KEY", default="insecure-key-change-me")
DEBUG = config("DEBUG", default=False, cast=bool)

# ALLOWED_HOSTS is frequently overridden by .env
# Make it resilient:
# - strip whitespace
# - drop empty entries
# - convert "*.domain" to ".domain" (Django expects leading dot, not wildcard)
# - always include "testserver" for Django test client
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


# ---------------------------------------------------------------
# Cloudflare + Nginx + Gunicorn
# ---------------------------------------------------------------
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

CSRF_TRUSTED_ORIGINS = [
    "https://narolims.reslab.dev",
    "https://www.narolims.reslab.dev",
    "http://narolims.reslab.dev",
]


# ===============================================================
# Installed apps
# ===============================================================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "lims_core.apps.LimsCoreConfig",
    "django_celery_results",
    "django_celery_beat",
]


# ===============================================================
# Middleware
# ===============================================================
MIDDLEWARE = [
    "lims_core.middleware.CurrentUserMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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
            "PASSWORD": config("DB_PASSWORD", default="StrongPasswordHere"),
            "HOST": config("DB_HOST", default="127.0.0.1"),
            "PORT": config("DB_PORT", default="5432"),
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
CORS_ALLOW_ALL_ORIGINS = True


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
    "VERSION": "0.1.0",
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "SERVERS": [
        {
            "url": "https://narolims.reslab.dev",
            "description": "Production",
        },
    ],
}


# ===============================================================
# JWT
# ===============================================================
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}


# ===============================================================
# Celery configuration
# ===============================================================
CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
CELERY_RESULT_BACKEND = "django-db"

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

CELERY_TIMEZONE = "Africa/Kampala"

CELERY_BEAT_SCHEDULE = {
    "scan-workflow-sla-every-10-mins": {
        "task": "lims_core.tasks.scan_workflow_sla",
        "schedule": crontab(minute="*/10"),
        "args": (),
    }
}
