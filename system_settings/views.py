# system_settings/views.py
import os
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect

from .forms import EmailSettingsForm, GiteaSettingsForm, OpenAISettingsForm
from .utils import (
    get_base_dir,
    write_env_file,
    update_env_file_keys,
    reload_django_process,
    restart_gitea_docker,
)


# ============================================================
#  Helpers para ler valores atuais do ambiente
# ============================================================

def _initial_email_from_env() -> dict:
    env = os.environ
    return {
        "email_backend": env.get(
            "EMAIL_BACKEND",
            "django.core.mail.backends.smtp.EmailBackend",
        ),
        "email_host": env.get("EMAIL_HOST", "smtp.gmail.com"),
        "email_port": int(env.get("EMAIL_PORT", "587") or 587),
        "email_use_tls": env.get("EMAIL_USE_TLS", "1") == "1",
        "email_use_ssl": env.get("EMAIL_USE_SSL", "0") == "1",
        "email_host_user": env.get("EMAIL_HOST_USER", ""),
        "email_host_password": env.get("EMAIL_HOST_PASSWORD", ""),
        "default_from_email": env.get(
            "DEFAULT_FROM_EMAIL",
            "TheManager <no-reply@example.com>",
        ),
        "server_email": env.get("SERVER_EMAIL", ""),
    }


def _initial_gitea_from_env() -> dict:
    env = os.environ
    return {
        "use_external_gitea": env.get("USE_EXTERNAL_GITEA", "0") == "1",

        "gitea_base_url": env.get("GITEA_BASE_URL", ""),
        "gitea_admin_token": env.get("GITEA_ADMIN_TOKEN", ""),

        "gitea_db_name": env.get("GITEA_DB_NAME", "gitea"),
        "gitea_db_user": env.get("GITEA_DB_USER", "gitea"),
        "mysql_root_password": env.get("MYSQL_ROOT_PASSWORD", ""),
        "mysql_password": env.get("MYSQL_PASSWORD", ""),

        "gitea_secret_key": env.get("GITEA_SECRET_KEY", ""),
        "gitea_internal_token": env.get("GITEA_INTERNAL_TOKEN", ""),
        "gitea_jwt_secret": env.get("GITEA_JWT_SECRET", ""),

        "gitea_admin_user": env.get("GITEA_ADMIN_USER", ""),
        "gitea_admin_pass": env.get("GITEA_ADMIN_PASS", ""),
        "gitea_admin_email": env.get("GITEA_ADMIN_EMAIL", ""),
    }


def _initial_openai_from_env() -> dict:
    """
    Lê as configurações de OpenAI / LLM compatível do ambiente.
    """
    env = os.environ
    return {
        "enable_openai": env.get("ENABLE_OPENAI", "0") == "1",
        "openai_api_base": env.get("OPENAI_API_BASE", "https://api.openai.com/v1"),
        "openai_api_key": env.get("OPENAI_API_KEY", ""),
        "openai_model": env.get("OPENAI_MODEL", "gpt-4.1-mini"),
        "openai_embeddings_model": env.get(
            "OPENAI_EMBEDDINGS_MODEL",
            "text-embedding-3-large",
        ),
    }


# Decorator simples para reaproveitar a regra de superusuário
def superuser_required(view_func):
    return login_required(user_passes_test(lambda u: u.is_superuser)(view_func))


# ============================================================
#  VIEW 1 — Tela inicial (resumo Email / Gitea / OpenAI)
# ============================================================

@superuser_required
def settings_home_view(request):
    """
    Tela inicial das configurações do sistema.
    Mostra um resumo e links para:
      - Configurações de e-mail
      - Configurações de Gitea
      - Configurações de OpenAI / LLM
    """
    email_initial = _initial_email_from_env()
    gitea_initial = _initial_gitea_from_env()
    openai_initial = _initial_openai_from_env()

    context = {
        "email_summary": {
            "host": email_initial["email_host"],
            "port": email_initial["email_port"],
            "default_from_email": email_initial["default_from_email"],
        },
        "gitea_summary": {
            "use_external_gitea": gitea_initial["use_external_gitea"],
            "base_url": gitea_initial["gitea_base_url"],
            "admin_user": gitea_initial["gitea_admin_user"],
        },
        "openai_summary": {
            "enabled": openai_initial["enable_openai"],
            "api_base": openai_initial["openai_api_base"],
            "model": openai_initial["openai_model"],
        },
    }
    return render(request, "system/settings_home.html", context)


# ============================================================
#  VIEW 2 — Configurações de E-MAIL
# ============================================================

@superuser_required
def email_settings_view(request):
    """
    Tela específica para configurar e-mail (usa .env.email).
    Ao salvar:
      - sobrescreve .env.email
      - tenta recarregar o Django (runserver/autoreload ou SIGHUP)
    """
    base_dir = get_base_dir()
    env_email_path: Path = base_dir / ".env.email"

    if request.method == "POST":
        form = EmailSettingsForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data

            email_data = {
                "EMAIL_BACKEND": cd["email_backend"],
                "EMAIL_HOST": cd["email_host"],
                "EMAIL_PORT": cd["email_port"],
                "EMAIL_USE_TLS": "1" if cd["email_use_tls"] else "0",
                "EMAIL_USE_SSL": "1" if cd["email_use_ssl"] else "0",
                "EMAIL_HOST_USER": cd["email_host_user"],
                "EMAIL_HOST_PASSWORD": cd["email_host_password"],
                "DEFAULT_FROM_EMAIL": cd["default_from_email"],
                "SERVER_EMAIL": cd["server_email"] or cd["default_from_email"],
            }

            write_env_file(
                env_email_path,
                email_data,
                header="# .env.email - Configurações de e-mail do TheManager",
            )

            # Recarregar Django
            reload_django_process()

            messages.success(
                request,
                "Configurações de e-mail salvas. O Django será recarregado.",
            )
            return redirect("system_settings:email_settings")
    else:
        form = EmailSettingsForm(initial=_initial_email_from_env())

    return render(
        request,
        "system/email_settings.html",
        {
            "form": form,
        },
    )


# ============================================================
#  VIEW 3 — Configurações de GITEA
# ============================================================

@superuser_required
def gitea_settings_view(request):
    """
    Tela específica para configurar Gitea.

    - Se 'use_external_gitea' estiver marcado:
        * Apenas salva GITEA_BASE_URL, GITEA_ADMIN_TOKEN e USE_EXTERNAL_GITEA
          no .env raiz (TheManager)
        * NÃO mexe em doker/getea/.env
        * NÃO reinicia Docker

    - Se NÃO estiver marcado (modo local):
        * Atualiza doker/getea/.env com DB, secrets, admin, etc.
        * Atualiza .env raiz com GITEA_BASE_URL, GITEA_ADMIN_TOKEN, USE_EXTERNAL_GITEA
        * Tenta rodar 'docker compose restart' em doker/getea
    """
    base_dir = get_base_dir()
    root_env_path: Path = base_dir / ".env"
    gitea_env_path: Path = base_dir / "doker" / "getea" / ".env"

    if request.method == "POST":
        form = GiteaSettingsForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            use_external = cd["use_external_gitea"]

            # 1) Sempre atualizar .env raiz para o Django saber como falar com o Gitea
            root_env_updates = {
                "USE_EXTERNAL_GITEA": "1" if use_external else "0",
                "GITEA_BASE_URL": cd["gitea_base_url"],
                "GITEA_ADMIN_TOKEN": cd["gitea_admin_token"],
            }

            update_env_file_keys(
                root_env_path,
                root_env_updates,
                header="# .env - Ambiente do TheManager (gerenciado parcialmente via painel)",
            )

            # 2) Se NÃO for externo, atualizar doker/getea/.env também
            if not use_external:
                gitea_env_updates = {
                    "GITEA_DB_NAME": cd["gitea_db_name"],
                    "GITEA_DB_USER": cd["gitea_db_user"],
                    "MYSQL_ROOT_PASSWORD": cd["mysql_root_password"],
                    "MYSQL_PASSWORD": cd["mysql_password"],

                    "GITEA_SECRET_KEY": cd["gitea_secret_key"],
                    "GITEA_INTERNAL_TOKEN": cd["gitea_internal_token"],
                    "GITEA_JWT_SECRET": cd["gitea_jwt_secret"],

                    "GITEA_ADMIN_USER": cd["gitea_admin_user"],
                    "GITEA_ADMIN_PASS": cd["gitea_admin_pass"],
                    "GITEA_ADMIN_EMAIL": cd["gitea_admin_email"],
                }

                if cd["gitea_base_url"]:
                    gitea_env_updates["GITEA_BASE_URL"] = cd["gitea_base_url"]
                if cd["gitea_admin_token"]:
                    gitea_env_updates["GITEA_ADMIN_TOKEN"] = cd["gitea_admin_token"]

                update_env_file_keys(
                    gitea_env_path,
                    gitea_env_updates,
                    header="# .env - Stack Gitea (DB, secrets, admin)",
                )

                # 3) Reiniciar Docker do Gitea local
                ok = restart_gitea_docker()
                if ok:
                    messages.success(
                        request,
                        "Configurações do Gitea local salvas e stack Docker reiniciado.",
                    )
                else:
                    messages.warning(
                        request,
                        "Configurações do Gitea local foram salvas, "
                        "mas não foi possível reiniciar o container automaticamente. "
                        "Execute 'docker compose restart' em doker/getea.",
                    )
            else:
                # Modo externo: só mudou URL/token no .env raiz
                messages.success(
                    request,
                    "Configurações de Gitea EXTERNO salvas. "
                    "O sistema usará a URL e o token informados.",
                )

            return redirect("system_settings:gitea_settings")
    else:
        form = GiteaSettingsForm(initial=_initial_gitea_from_env())

    return render(
        request,
        "system/gitea_settings.html",
        {
            "form": form,
        },
    )


# ============================================================
#  VIEW 4 — Configurações de OPENAI / LLM
# ============================================================

@superuser_required
def openai_settings_view(request):
    """
    Tela específica para configurar integração com OpenAI / provedores compatíveis.

    Ao salvar:
      - Atualiza o .env raiz com:
          ENABLE_OPENAI
          OPENAI_API_BASE
          OPENAI_API_KEY
          OPENAI_MODEL
          OPENAI_EMBEDDINGS_MODEL
      - Tenta recarregar o Django para que novas configs entrem em vigor.
    """
    base_dir = get_base_dir()
    root_env_path: Path = base_dir / ".env"

    if request.method == "POST":
        form = OpenAISettingsForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data

            updates = {
                "ENABLE_OPENAI": "1" if cd["enable_openai"] else "0",
                "OPENAI_API_BASE": cd["openai_api_base"],
                "OPENAI_API_KEY": cd["openai_api_key"],
                "OPENAI_MODEL": cd["openai_model"],
                "OPENAI_EMBEDDINGS_MODEL": cd["openai_embeddings_model"],
            }

            update_env_file_keys(
                root_env_path,
                updates,
                header="# .env - Ambiente do TheManager (OpenAI / LLM settings gerenciados via painel)",
            )

            # Recarregar Django para aplicar novas configs
            reload_django_process()

            messages.success(
                request,
                "Configurações de OpenAI / LLM salvas. O Django será recarregado.",
            )
            return redirect("system_settings:openai_settings")
    else:
        form = OpenAISettingsForm(initial=_initial_openai_from_env())

    return render(
        request,
        "system/openai_settings.html",
        {
            "form": form,
        },
    )
