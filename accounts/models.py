# accounts/models.py
from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
from datetime import timedelta


class User(AbstractUser):
    """
    Custom user model com:
    - Hierarquia de papeis (role)
    - Campos de integração com Gitea (espelho de preferências/perfil)
    - Helpers de permissão que consideram 'role' e 'is_superuser'
    """

    # =========================
    # Roles
    # =========================
    ROLE_ADMIN   = "admin"
    ROLE_MANAGER = "manager"
    ROLE_SENIOR  = "senior"
    ROLE_REGULAR = "regular"
    ROLE_JUNIOR  = "junior"

    ROLE_CHOICES = [
        (ROLE_ADMIN,   "Admin"),
        (ROLE_MANAGER, "Manager"),
        (ROLE_SENIOR,  "Senior"),
        (ROLE_REGULAR, "Regular"),
        (ROLE_JUNIOR,  "Junior"),
    ]

    # e-mail único (substitui o email padrão do AbstractUser)
    email = models.EmailField("email address", unique=True)

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_REGULAR,
        help_text="Controls allowed actions inside the system.",
        db_index=True,
    )

    # =========================
    # Gitea integration (perfil e preferências)
    # =========================
    gitea_id = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="User ID in Gitea",
    )
    gitea_avatar_url = models.URLField(null=True, blank=True)

    # Guarda a base URL do Gitea usada na sincronização (útil para multi-ambiente)
    gitea_url = models.URLField(
        null=True, blank=True,
        help_text="Gitea base URL used for automatic sync",
    )

    # Timestamp local para rastrear quando espelhamos senha no Gitea
    password_updated_at = models.DateTimeField(null=True, blank=True)

    gitea_max_repo_creation = models.IntegerField(
        null=True, blank=True,
        help_text="Max number of repos user can create (None = server default)",
    )

    GITEA_VISIBILITY_CHOICES = (
        ("public", "public"),
        ("limited", "limited"),
        ("private", "private"),
    )
    gitea_visibility = models.CharField(
        max_length=16,
        choices=GITEA_VISIBILITY_CHOICES,
        null=True, blank=True,
        help_text="Gitea profile visibility",
    )

    # Flags de preferência/limitação no Gitea
    gitea_allow_create_organization = models.BooleanField(null=True, blank=True, default=None)
    gitea_allow_git_hook = models.BooleanField(null=True, blank=True, default=None)
    gitea_allow_import_local = models.BooleanField(null=True, blank=True, default=None)
    gitea_restricted = models.BooleanField(null=True, blank=True, default=None)
    gitea_prohibit_login = models.BooleanField(null=True, blank=True, default=None)

    # Campos de perfil do Gitea
    gitea_full_name = models.CharField(max_length=255, null=True, blank=True)
    gitea_website = models.URLField(null=True, blank=True)
    gitea_location = models.CharField(max_length=255, null=True, blank=True)
    gitea_description = models.TextField(null=True, blank=True)

    # =========================
    # Helpers
    # =========================
    def __str__(self) -> str:  # pragma: no cover
        return self.username or self.email

    @property
    def display_name(self) -> str:
        """Melhor rótulo disponível para exibição."""
        return self.get_full_name() or self.username or self.email

    # --------- simple role checks ---------
    def is_admin(self) -> bool:
        return self.role == self.ROLE_ADMIN

    def is_manager(self) -> bool:
        return self.role == self.ROLE_MANAGER

    def is_senior(self) -> bool:
        return self.role == self.ROLE_SENIOR

    def is_regular(self) -> bool:
        return self.role == self.ROLE_REGULAR

    def is_junior(self) -> bool:
        return self.role == self.ROLE_JUNIOR

    # =========================
    # Permission helpers (consideram is_superuser)
    # =========================
    @property
    def can_manage_users(self) -> bool:
        """
        Admin + Manager podem gerenciar usuários.
        Superuser SEMPRE pode.
        """
        return self.is_superuser or self.is_admin() or self.is_manager()

    @property
    def can_delete_users(self) -> bool:
        """
        Remoção de usuários: apenas Admin… mas superuser SEMPRE pode.
        """
        return self.is_superuser or self.is_admin()

    @property
    def can_create_projects(self) -> bool:
        return self.is_superuser or self.is_admin() or self.is_manager()

    @property
    def can_manage_projects(self) -> bool:
        return self.is_superuser or self.is_admin() or self.is_manager()

    @property
    def can_edit_self(self) -> bool:
        return True

    # Normalização antes de salvar (e-mail sempre lower/strip)
    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        # Se desejar, descomente para forçar username minúsculo:
        # if self.username:
        #     self.username = self.username.strip().lower()
        return super().save(*args, **kwargs)

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["date_joined"]


# ======================================================
# User Invite Token (ativação e reset por link único)
# ======================================================
class UserInvite(models.Model):
    """
    Token one-time para permitir que um usuário convidado defina a senha e ative a conta.
    Fluxo típico:
      - Admin/Manager cria User (inativo, senha inutilizável)
      - Cria-se o token de convite → envia por e-mail (ou copia o link)
      - Usuário abre o link, define a senha → conta ativa → token é consumido (deletado)
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="invite",
    )
    token = models.CharField(
        max_length=72,
        unique=True,
        db_index=True,
        help_text="One-time token for password setup",
    )
    created_at = models.DateTimeField(default=timezone.now)

    # Expiração opcional do token
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="If defined, tokens beyond this point are invalid.",
    )

    # status helpers
    def is_expired(self) -> bool:
        return bool(self.expires_at and timezone.now() >= self.expires_at)

    @staticmethod
    def create_for_user(user: User, *, validity_days: int | None = 7) -> "UserInvite":
        """
        Cria (ou substitui) um token novo para o usuário informado.
        """
        UserInvite.objects.filter(user=user).delete()

        token = get_random_string(56)
        expires = (
            timezone.now() + timedelta(days=validity_days)
            if validity_days
            else None
        )

        return UserInvite.objects.create(
            user=user,
            token=token,
            expires_at=expires,
        )

        return UserInvite.objects.create(
            user=user,
            token=token,
            expires_at=expires,
        )

    def __str__(self) -> str:  # pragma: no cover
        return f"Invite<{self.user_id}>"
