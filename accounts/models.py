#accounts/models.py
from __future__ import annotations
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


def user_avatar_upload_to(instance: "User", filename: str) -> str:
    # Ex.: avatars/42/2025-10-27_avatar.png
    return f"avatars/{instance.pk or 'new'}/{timezone.now().date()}_{filename}"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("Email é obrigatório.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        # por padrão, nenhum papel → sem acesso até alguém marcar
        extra_fields.setdefault("is_system_manager", False)
        extra_fields.setdefault("is_employee", False)
        extra_fields.setdefault("is_client", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        # superuser tem acesso ao Django Admin; flags de papel são opcionais
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser precisa is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser precisa is_superuser=True.")

        # você pode, se quiser, dar todas as flags ao superuser:
        extra_fields.setdefault("is_system_manager", True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Usuário minimalista: email+senha, avatar opcional e flags de acesso ao sistema.
    Sem qualquer relação com 'project' (outro app).
    """

    # Credenciais
    email = models.EmailField(unique=True, db_index=True)

    # Perfil
    avatar = models.ImageField(upload_to=user_avatar_upload_to, blank=True, null=True)

    # Flags de PAPEL no sistema (qualquer combinação é possível)
    is_system_manager = models.BooleanField(default=False)  # gerente do sistema (admin funcional)
    is_employee = models.BooleanField(default=False)        # funcionário (usuário interno)
    is_client = models.BooleanField(default=False)          # cliente (acesso restrito)

    # (opcional) custo/hora p/ relatórios
    hourly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(0)]
    )

    # Django flags
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # acesso ao Django admin
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["is_system_manager"]),
            models.Index(fields=["is_employee"]),
            models.Index(fields=["is_client"]),
        ]

    def __str__(self) -> str:
        return self.email

    # ===== Helpers =====
    @property
    def has_any_role(self) -> bool:
        """Tem pelo menos uma flag de papel?"""
        return bool(self.is_system_manager or self.is_employee or self.is_client)

    @property
    def is_denied_for_system(self) -> bool:
        """Sem papel algum → sem acesso ao sistema (fora tela de login)."""
        if self.is_superuser:
            return False  # superuser sempre entra
        return not self.has_any_role

    def avatar_url(self) -> str:
        return self.avatar.url if self.avatar else "https://placehold.co/128x128?text=User"
