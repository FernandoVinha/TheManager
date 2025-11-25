from __future__ import annotations

import logging
import secrets
import string
from typing import Any, Dict, Optional

from django.conf import settings
from django.db import transaction
from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone as dj_tz

from .models import User, UserInvite
from .services import gitea as gitea_api

log = logging.getLogger(__name__)


def _rand_pwd(n: int = 24) -> str:
    """Gera uma senha randômica com caracteres seguros para uso interno.
    Não registra essa senha em logs.
    """
    alphabet = string.ascii_letters + string.digits + "!@#%^_+=-"
    return "".join(secrets.choice(alphabet) for _ in range(n))


# -------------------------
# pre_save: captura username antigo (para rename)
# -------------------------
@receiver(pre_save, sender=User)
def capture_old_username(sender: type[User], instance: User, **kwargs) -> None:
    """
    Armazena username antigo em atributo efêmero `._old_username` para usar
    no post_save e decidir se precisamos renomear no Gitea.
    """
    if instance.pk:
        try:
            old = sender.objects.only("username").get(pk=instance.pk)
            instance._old_username = old.username
        except sender.DoesNotExist:
            instance._old_username = None
    else:
        instance._old_username = None


# -------------------------
# post_save: sincroniza com Gitea (create, update, rename, password)
# -------------------------
@receiver(post_save, sender=User)
def sync_user_to_gitea(sender: type[User], instance: User, created: bool, **kwargs) -> None:
    """
    Sincroniza usuário com Gitea:
      - create: cria usuário no Gitea após commit
      - update: renomeia / atualiza fields após commit
      - password: troca senha no Gitea após commit quando habilitado
    Erros são logados mas não abortam o fluxo do Django.
    """
    base_url = getattr(settings, "GITEA_BASE_URL", None)
    if base_url and instance.gitea_url != base_url:
        # Mantém a base do Gitea registrada no user para referência futura
        sender.objects.filter(pk=instance.pk).update(gitea_url=base_url)

    desired_username = instance.username
    desired_email = instance.email
    desired_admin = bool(instance.is_superuser)

    # ====== CREATE ======
    if created:
        # Captura o raw password (se houver) e decide o que usar já no momento do save,
        # para evitar depender de `instance` dentro do on_commit.
        raw_password_value: Optional[str] = getattr(instance, "_raw_password_value", None)
        use_password: str
        if getattr(settings, "GITEA_SYNC_PASSWORD", False) and raw_password_value:
            use_password = raw_password_value
        elif getattr(settings, "GITEA_SYNC_PASSWORD", False):
            # GITEA_SYNC_PASSWORD habilitado mas não há senha crua disponível:
            # gera uma aleatória para envio ao Gitea (não será logada).
            use_password = _rand_pwd()
        else:
            # Não sincroniza senha com Gitea; gera password aleatória para criação no Gitea.
            use_password = _rand_pwd()

        visibility = instance.gitea_visibility or None
        full_name = instance.gitea_full_name or instance.get_full_name() or None
        max_repo_creation = instance.gitea_max_repo_creation
        allow_create_org = instance.gitea_allow_create_organization
        restricted = instance.gitea_restricted
        prohibit_login_flag = getattr(settings, "GITEA_PROHIBIT_LOGIN", False)
        website = instance.gitea_website or None
        location = instance.gitea_location or None
        description = instance.gitea_description or None

        def _after_commit_create(user_pk: int, username: str, email: str, is_admin: bool, password_to_use: str, payload_kwargs: Dict[str, Any]):
            """Cria usuário no Gitea e atualiza campos locais com o retorno (id, avatar)."""
            try:
                payload = gitea_api.create_user(
                    username=username,
                    email=email,
                    password=password_to_use,
                    is_admin=is_admin,
                    visibility=payload_kwargs.get("visibility"),
                    full_name=payload_kwargs.get("full_name"),
                    max_repo_creation=payload_kwargs.get("max_repo_creation"),
                    allow_create_organization=payload_kwargs.get("allow_create_organization"),
                    restricted=payload_kwargs.get("restricted"),
                    prohibit_login=payload_kwargs.get("prohibit_login"),
                    website=payload_kwargs.get("website"),
                    location=payload_kwargs.get("location"),
                    description=payload_kwargs.get("description"),
                )

                # Atualiza campos locais; não expõe payload completo em logs
                sender.objects.filter(pk=user_pk).update(
                    gitea_id=payload.get("id"),
                    gitea_avatar_url=payload.get("avatar_url"),
                )
            except Exception:
                # Log detalhado sem imprimir tokens/senhas
                log.exception("Falha ao criar usuário no Gitea (user=%s).", username)

        payload_args = {
            "visibility": visibility,
            "full_name": full_name,
            "max_repo_creation": max_repo_creation,
            "allow_create_organization": allow_create_org,
            "restricted": restricted,
            "prohibit_login": prohibit_login_flag,
            "website": website,
            "location": location,
            "description": description,
        }

        # Agenda criação após commit da transação
        transaction.on_commit(lambda: _after_commit_create(instance.pk, desired_username, desired_email, desired_admin, use_password, payload_args))
        # Limpa flags/valores efêmeros relacionados à senha
        if hasattr(instance, "_raw_password_changed"):
            instance._raw_password_changed = False
        if hasattr(instance, "_raw_password_value"):
            try:
                delattr(instance, "_raw_password_value")
            except Exception:
                # operação de limpeza não crítica
                pass
        return

    # ====== UPDATE ======
    # 1) rename — se username foi alterado
    old_username = getattr(instance, "_old_username", None)
    if old_username and old_username != desired_username:
        def _after_commit_rename(old_u: str, new_u: str):
            try:
                gitea_api.rename_user(old_username=old_u, new_username=new_u)
            except Exception:
                log.exception("Falha ao renomear usuário no Gitea (%s -> %s).", old_u, new_u)
        transaction.on_commit(lambda: _after_commit_rename(old_username, desired_username))

    # 2) patch idempotente (campos que podem ser atualizados)
    patch_kwargs: Dict[str, Any] = {
        "email": desired_email,
        "is_admin": desired_admin,
    }
    if instance.gitea_max_repo_creation is not None:
        try:
            patch_kwargs["max_repo_creation"] = int(instance.gitea_max_repo_creation)
        except (TypeError, ValueError):
            log.warning("gitea_max_repo_creation inválido para user=%s: %r", instance.pk, instance.gitea_max_repo_creation)
    if instance.gitea_visibility:
        patch_kwargs["visibility"] = instance.gitea_visibility
    if instance.gitea_full_name or instance.get_full_name():
        patch_kwargs["full_name"] = instance.gitea_full_name or instance.get_full_name()
    if instance.gitea_website:
        patch_kwargs["website"] = instance.gitea_website
    if instance.gitea_location:
        patch_kwargs["location"] = instance.gitea_location
    if instance.gitea_description:
        patch_kwargs["description"] = instance.gitea_description

    def _after_commit_patch(username: str, payload: Dict[str, Any]):
        try:
            updated = gitea_api.patch_user(username=username, **payload)
            if updated:
                # Atualiza avatar local se mudou
                sender.objects.filter(pk=instance.pk).update(
                    gitea_avatar_url=updated.get("avatar_url", instance.gitea_avatar_url),
                )
        except Exception as exc:
            # Tratamento específico para 422 (Unprocessable Entity) — ignora
            msg = str(exc)
            if "HTTP Error 422" in msg or "Unprocessable Entity" in msg:
                log.warning("PATCH 422 no Gitea para usuário %s — campo inválido ou sem alterações: %s", username, msg)
            else:
                log.exception("Falha ao atualizar usuário no Gitea (%s): %s", username, msg)

    transaction.on_commit(lambda: _after_commit_patch(desired_username, patch_kwargs))

    # 3) senha — espelha após commit quando habilitado e flagada como alterada
    if getattr(settings, "GITEA_SYNC_PASSWORD", False) and getattr(instance, "_raw_password_changed", False):
        # captura e limpa a senha efêmera imediatamente
        new_pwd = getattr(instance, "_raw_password_value", None)
        instance._raw_password_changed = False
        if hasattr(instance, "_raw_password_value"):
            try:
                delattr(instance, "_raw_password_value")
            except Exception:
                pass

        if new_pwd:
            def _after_commit_pwd(username: str, pwd: str, user_pk: int):
                try:
                    gitea_api.change_password(username=username, new_password=pwd)
                    sender.objects.filter(pk=user_pk).update(password_updated_at=dj_tz.now())
                except Exception:
                    log.exception("Falha ao trocar senha no Gitea para usuário %s.", username)

            transaction.on_commit(lambda: _after_commit_pwd(desired_username, new_pwd, instance.pk))


# -------------------------
# pre_delete: tenta deletar usuário no Gitea (sem abortar exclusão local)
# -------------------------
@receiver(pre_delete, sender=User)
def delete_user_in_gitea(sender: type[User], instance: User, **kwargs) -> None:
    """
    Tenta deletar (ou marcar purge) o usuário no Gitea.
    Falhas são apenas logadas e não impedem exclusão local.
    """
    username = instance.username
    try:
        # Não passamos dados sensíveis e tratamos exceções localmente
        gitea_api.delete_user(username=username, purge=False)
    except Exception:
        log.warning("Falha ao deletar usuário no Gitea (%s) — operação ignorada.", username)
