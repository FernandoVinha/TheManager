# accounts/signals.py
from __future__ import annotations
import logging, secrets, string
from datetime import datetime, timezone
from django.conf import settings
from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver
from .models import User
from .services import gitea as gitea_api

log = logging.getLogger(__name__)

def _rand_pwd(n: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#%^_+=-"
    return "".join(secrets.choice(alphabet) for _ in range(n))

@receiver(pre_save, sender=User)
def capture_old_username(sender, instance: User, **kwargs):
    """Guarda o username antigo para suportar rename sem precisar de campo cache."""
    if instance.pk:
        try:
            old = sender.objects.only("username").get(pk=instance.pk)
            instance._old_username = old.username  # atributo efêmero
        except sender.DoesNotExist:
            instance._old_username = None
    else:
        instance._old_username = None

@receiver(post_save, sender=User)
def sync_user_to_gitea(sender, instance: User, created: bool, **kwargs):
    base_url = getattr(settings, "GITEA_BASE_URL", None)
    if base_url and instance.gitea_url != base_url:
        sender.objects.filter(pk=instance.pk).update(gitea_url=base_url)

    desired_username = instance.username
    desired_email = instance.email
    desired_admin = bool(instance.is_superuser)

    # ===== CREATE =====
    if created:
        if getattr(settings, "GITEA_SYNC_PASSWORD", False):
            raw_pwd = getattr(instance, "_raw_password_value", None) or getattr(instance, "_password", None) or _rand_pwd()
        else:
            raw_pwd = _rand_pwd()

        try:
            payload = gitea_api.create_user(
                username=desired_username,
                email=desired_email,
                password=raw_pwd,
                is_admin=desired_admin,
                visibility=instance.gitea_visibility or None,
                full_name=(instance.gitea_full_name or instance.get_full_name() or None),
                max_repo_creation=instance.gitea_max_repo_creation,
                allow_create_organization=instance.gitea_allow_create_organization,
                restricted=instance.gitea_restricted,
                prohibit_login=getattr(settings, "GITEA_PROHIBIT_LOGIN", False),
                website=instance.gitea_website or None,
                location=instance.gitea_location or None,
                description=instance.gitea_description or None,
            )
        except Exception as e:
            log.exception("Falha ao criar usuário no Gitea (%s): %s", desired_username, e)
            raise

        sender.objects.filter(pk=instance.pk).update(
            gitea_id=payload.get("id"),
            gitea_avatar_url=payload.get("avatar_url"),
        )

        if hasattr(instance, "_raw_password_changed"):
            instance._raw_password_changed = False
        if hasattr(instance, "_raw_password_value"):
            delattr(instance, "_raw_password_value")
        return

    # ===== UPDATE =====
    # rename se mudou de fato
    old_username = getattr(instance, "_old_username", None)
    if old_username and old_username != desired_username:
        try:
            gitea_api.rename_user(old_username=old_username, new_username=desired_username)
        except Exception as e:
            log.exception("Falha ao renomear usuário no Gitea (%s -> %s): %s",
                          old_username, desired_username, e)
            raise

    # patch — sempre idempotente (Gitea ignora o que não muda)
    patch_kwargs = {
        "email": desired_email,
        "is_admin": desired_admin,
    }
    if instance.gitea_max_repo_creation is not None:
        patch_kwargs["max_repo_creation"] = int(instance.gitea_max_repo_creation)
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

    try:
        updated = gitea_api.patch_user(username=desired_username, **patch_kwargs)
        if updated:
            sender.objects.filter(pk=instance.pk).update(
                gitea_avatar_url=updated.get("avatar_url", instance.gitea_avatar_url),
            )
    except Exception as e:
        msg = str(e)
        if "HTTP Error 422" in msg or "Unprocessable Entity" in msg:
            log.warning("PATCH 422 no Gitea para usuário %s — ignorando: %s", desired_username, msg)
        else:
            log.exception("Falha ao atualizar usuário no Gitea (%s): %s", desired_username, e)
            raise

    # senha — espelha se a flag estiver ligada
    if getattr(settings, "GITEA_SYNC_PASSWORD", False) and getattr(instance, "_raw_password_changed", False):
        try:
            gitea_api.change_password(username=desired_username, new_password=instance._raw_password_value)
            sender.objects.filter(pk=instance.pk).update(password_updated_at=datetime.now(timezone.utc))
        except Exception as e:
            log.exception("Falha ao trocar senha no Gitea (%s): %s", desired_username, e)
        finally:
            instance._raw_password_changed = False
            if hasattr(instance, "_raw_password_value"):
                delattr(instance, "_raw_password_value")

@receiver(pre_delete, sender=User)
def delete_user_in_gitea(sender, instance: User, **kwargs):
    try:
        gitea_api.delete_user(username=instance.username, purge=False)
    except Exception as e:
        log.warning("Falha ao deletar usuário no Gitea (%s): %s (ignorado)", instance.username, e)

# --------- hook para capturar senha crua ---------
_original_set_password = User.set_password
def _set_password_and_flag(self: User, raw_password: str):
    self._raw_password_changed = True
    self._raw_password_value = raw_password
    return _original_set_password(self, raw_password)
User.set_password = _set_password_and_flag  # type: ignore[assignment]
