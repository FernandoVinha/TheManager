"""
Django settings for core project — DEV (corrigido)
"""

from __future__ import annotations
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
# ------------------------------------------------------

# Observação: seu instalador usa "doker/getea" — mantive esse caminho.
GETEA_ENV = BASE_DIR / "doker" / "getea" / ".env"
ROOT_ENV = BASE_DIR / ".env"
EMAIL_ENV = BASE_DIR / ".env.email"

# Carrega variáveis de e-mail separadamente (se existir)
if EMAIL_ENV.exists():
    load_dotenv(EMAIL_ENV, override=True)

if GETEA_ENV.exists():
    load_dotenv(GETEA_ENV, override=False)

if ROOT_ENV.exists():
    load_dotenv(ROOT_ENV, override=False)


# ======================================================
# HELPERS
# ======================================================

def env_bool(value, default: bool = False) -> bool:
    """Converte vários formatos de env para boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def env_list(value, default: list[str] | None = None, sep: str = ",") -> list[str]:
    """Converte string coma-separada em lista, limpa espaços."""
    if value is None:
        return default or []
    return [p.strip() for p in str(value).split(sep) if p.strip()]


# ======================================================
# CONFIG BÁSICA
# ======================================================

# DEBUG controlado por env (DJANGO_DEBUG) — seu instalador define DJANGO_DEBUG=1 em DEV
DEBUG = env_bool(os.environ.get("DJANGO_DEBUG"), default=True)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY and not DEBUG:
    raise RuntimeError("DJANGO_SECRET_KEY não definido em ambiente de produção (variável DJANGO_SECRET_KEY).")

# ALLOWED_HOSTS: aceita valor em .env como "127.0.0.1,localhost,192.168.1.161"
ALLOWED_HOSTS = env_list(os.environ.get("ALLOWED_HOSTS"), default=(["127.0.0.1", "localhost"] if DEBUG else []))

# CSRF trusted origins: incluir hosts com esquema se fornecido, e localhost dev padrão
CSRF_TRUSTED_ORIGINS = []
for host in ALLOWED_HOSTS:
    if host.startswith("http://") or host.startswith("https://"):
        CSRF_TRUSTED_ORIGINS.append(host)
    else:
        # adiciona entradas locais padrão (porta 8000)
        CSRF_TRUSTED_ORIGINS.append(f"http://{host}:8000")
        CSRF_TRUSTED_ORIGINS.append(f"https://{host}")

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

    # seus apps
    "accounts",
    "projects",
    "task",  # verifique se o nome do app no projeto é realmente "task" (corrigi "tasck")
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
# URLS / TEMPLATES / WSGI
# ======================================================

ROOT_URLCONF = "core.urls"

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

WSGI_APPLICATION = "core.wsgi.application"


# ======================================================
# DATABASE
# ======================================================

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

LANGUAGE_CODE = os.environ.get("DJANGO_LANGUAGE_CODE", "pt-br")
TIME_ZONE = os.environ.get("DJANGO_TIME_ZONE", "America/Sao_Paulo")
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
# SESSIONS / COOKIES / SEGURANÇA
# ======================================================

SESSION_ENGINE = "django.contrib.sessions.backends.db"

SESSION_COOKIE_NAME = "themanager_sessionid"
CSRF_COOKIE_NAME = "themanager_csrftoken"

# Em produção (DEBUG=False) forçamos cookies seguros
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.environ.get("CSRF_COOKIE_SAMESITE", "Lax")

# Segurança extra para produção
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool(os.environ.get("SECURE_SSL_REDIRECT"), default=True)
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", 60 * 60 * 24 * 7))  # 1 semana por padrão
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(os.environ.get("SECURE_HSTS_INCLUDE_SUBDOMAINS"), default=True)
    SECURE_HSTS_PRELOAD = env_bool(os.environ.get("SECURE_HSTS_PRELOAD"), default=True)
    X_FRAME_OPTIONS = os.environ.get("X_FRAME_OPTIONS", "DENY")


# ======================================================
# EMAIL — SMTP
# ======================================================

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend",
)

EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool(os.environ.get("EMAIL_USE_TLS"), default=True)
EMAIL_USE_SSL = env_bool(os.environ.get("EMAIL_USE_SSL"), default=False)

DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    "TheManager <no-reply@example.com>",
)
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)


# ======================================================
# GITEA
# ======================================================

def _read_app_ini_root_url() -> str | None:
    """Tenta ler app.ini do Gitea na pasta doker/getea (conforme seu instalador)."""
    app_ini = BASE_DIR / "doker" / "getea" / "gitea" / "config" / "app.ini"
    if not app_ini.exists():
        return None
    cfg = configparser.ConfigParser()
    cfg.read(app_ini)
    for sect in ("server", "Server", "SERVER"):
        if cfg.has_section(sect) and cfg.has_option(sect, "ROOT_URL"):
            return cfg.get(sect, "ROOT_URL").rstrip("/")
    return None


_gitea_base = os.environ.get("GITEA_BASE_URL") or os.environ.get("ROOT_URL")
_gitea_token = os.environ.get("GITEA_ADMIN_TOKEN")

if not _gitea_base:
    _gitea_base = _read_app_ini_root_url()
if not _gitea_base:
    _gitea_base = "http://localhost:3000"

GITEA_BASE_URL = _gitea_base
GITEA_ADMIN_TOKEN = _gitea_token or ""

GITEA_APP_INI = str(BASE_DIR / "doker" / "getea" / "gitea" / "config" / "app.ini")


if DEBUG and not GITEA_ADMIN_TOKEN:
    import logging
    logging.getLogger(__name__).warning(
        "⚠️  GITEA_ADMIN_TOKEN não encontrado! Criação de usuários/repos ignorada até configurar."
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
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}


# ======================================================
# DEFAULT PRIMARY KEY
# ======================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
