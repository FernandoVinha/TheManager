"""
Django settings for core project — DEV ONLY
"""

import os
import configparser
from pathlib import Path
from dotenv import load_dotenv

# ======================================================
# BASE
# ======================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# ------------------------------------------------------
# Carrega variáveis de ambiente o mais cedo possível
# (para DB, Django, Gitea, etc.)
# ------------------------------------------------------

GETEA_ENV = BASE_DIR / "doker" / "getea" / ".env"
ROOT_ENV = BASE_DIR / ".env"


# Carrega primeiro getea/.env criado pelo instalador
if GETEA_ENV.exists():
    load_dotenv(GETEA_ENV, override=False)

# Depois tenta carregar .env raiz (sem sobrescrever)
if ROOT_ENV.exists():
    load_dotenv(ROOT_ENV, override=False)

# ======================================================
# CONFIG BÁSICA
# ======================================================

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-CHANGE-ME-IN-PROD")
DEBUG = True  # Em prod, trocar para usar env, ex: os.environ.get("DJANGO_DEBUG") == "1"

ALLOWED_HOSTS = ["*", "127.0.0.1", "localhost"]
CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

# ======================================================
# APPS
# ======================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "accounts",
    "projects",
    "tasck",
]

AUTH_USER_MODEL = "accounts.User"


# ======================================================
# MIDDLEWARE
# ======================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ======================================================
# URLS
# ======================================================

ROOT_URLCONF = "core.urls"


# ======================================================
# TEMPLATES
# ======================================================

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
                "accounts.context_processors.user_role_context",
            ],
        },
    },
]


# ======================================================
# WSGI
# ======================================================

WSGI_APPLICATION = "core.wsgi.application"


# ======================================================
# DB
# ======================================================
# Se tiver variáveis de Postgres no ambiente (ex: via Docker),
# usa Postgres. Caso contrário, cai para SQLite (dev local).

if os.environ.get("POSTGRES_DB") or os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "themanager"),
            "USER": os.environ.get("POSTGRES_USER", "themanager"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "themanager"),
            "HOST": os.environ.get("POSTGRES_HOST", "db"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ======================================================
# PASSWORD VALIDATION
# ======================================================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ======================================================
# TIME & LANGUAGE
# ======================================================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"  # se quiser, pode trocar depois para "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True


# ======================================================
# STATIC / MEDIA
# ======================================================

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# ======================================================
# AUTH FLOW
# ======================================================

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "login"


# ======================================================
# SESSIONS / COOKIES
# ======================================================

SESSION_ENGINE = "django.contrib.sessions.backends.db"

SESSION_COOKIE_NAME = "themanager_sessionid"
CSRF_COOKIE_NAME = "themanager_csrftoken"

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"


# ======================================================
# EMAIL
# ======================================================

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "TheManager <no-reply@example.com>"


# ======================================================
# GITEA
# ======================================================

def _read_app_ini_root_url() -> str | None:
    """
    Lê ROOT_URL do getea/gitea/config/app.ini, caso exista.
    """
    app_ini = BASE_DIR / "doker" / "getea" / "gitea" / "config" / "app.ini"

    if not app_ini.exists():
        return None

    cfg = configparser.ConfigParser()
    cfg.read(app_ini)

    for sect in ("server", "Server", "SERVER"):
        if cfg.has_section(sect) and cfg.has_option(sect, "ROOT_URL"):
            return cfg.get(sect, "ROOT_URL").rstrip("/")
    return None


# 1) pega do ambiente
_gitea_base = (
    os.environ.get("GITEA_BASE_URL") or
    os.environ.get("ROOT_URL")
)

_gitea_token = os.environ.get("GITEA_ADMIN_TOKEN")

# 2) fallback da URL → app.ini
if not _gitea_base:
    _gitea_base = _read_app_ini_root_url()

# 3) fallback final
if not _gitea_base:
    _gitea_base = "http://localhost:3000"

GITEA_BASE_URL = _gitea_base
GITEA_ADMIN_TOKEN = _gitea_token or ""

GITEA_APP_INI = str(
    BASE_DIR / "doker" / "getea" / "gitea" / "config" / "app.ini"
)


# Loga aviso se DEBUG e token ausente
if DEBUG and not GITEA_ADMIN_TOKEN:
    import logging
    logging.getLogger(__name__).warning(
        "⚠️  GITEA_ADMIN_TOKEN não encontrado! "
        "Criação de usuários/repos ignorada até configurar."
    )


# ======================================================
# LOG
# ======================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "django.contrib.sessions": {"handlers": ["console"], "level": "WARNING"},
        "django.security.csrf": {"handlers": ["console"], "level": "WARNING"},
    },
}


# ======================================================
# DEFAULT PRIMARY KEY
# ======================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
