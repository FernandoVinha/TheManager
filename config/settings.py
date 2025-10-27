"""
Django settings for config project.
"""

from pathlib import Path
import os

# Base
BASE_DIR = Path(__file__).resolve().parent.parent

# =========================
# Segurança / Ambiente
# =========================
# Em produção, use variável de ambiente!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = ["*"]

# =========================
# Apps
# =========================
INSTALLED_APPS = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Seus apps
    "accounts",
]

# User customizado
AUTH_USER_MODEL = "accounts.User"

# =========================
# Middleware / URLs / WSGI
# =========================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # adicione pastas de templates se usar fora dos apps:
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # flags de papel (manager/employee/client) nos templates
                "accounts.context_processors.roles_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# =========================
# Banco de Dados
# =========================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# =========================
# Senhas
# =========================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# =========================
# I18N / TZ
# =========================
LANGUAGE_CODE = "pt-br"          # troque para 'en-us' se preferir
TIME_ZONE = "America/Sao_Paulo"  # sua TZ
USE_I18N = True
USE_TZ = True

# =========================
# Arquivos Estáticos / Mídia
# =========================
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]  # opcional: assets do projeto
STATIC_ROOT = BASE_DIR / "staticfiles"    # onde o collectstatic junta tudo (prod)

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# =========================
# Django padrão
# =========================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =========================
# Login (opcional, útil já)
# =========================
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# =========================
# CSRF (ajuste se usar domínio)
# =========================
# CSRF_TRUSTED_ORIGINS = ["https://seu-dominio.com"]
