from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string


class User(AbstractUser):
    """
    Custom user model with:
    - Role hierarchy for project administration
    - Gitea integration fields
    - Convenience permission helpers
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

    # override email → unique
    email = models.EmailField("email address", unique=True)

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_REGULAR,
        help_text="Controls allowed actions inside the system.",
    )

    # =========================
    # Gitea integration
    # =========================
    gitea_id = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="User ID in Gitea",
    )
    gitea_avatar_url = models.URLField(null=True, blank=True)
    gitea_url = models.URLField(
        null=True, blank=True,
        help_text="Gitea base URL used for automatic sync",
    )

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

    gitea_allow_create_organization = models.BooleanField(default=None, null=True, blank=True)
    gitea_allow_git_hook = models.BooleanField(default=None, null=True, blank=True)
    gitea_allow_import_local = models.BooleanField(default=None, null=True, blank=True)
    gitea_restricted = models.BooleanField(default=None, null=True, blank=True)
    gitea_prohibit_login = models.BooleanField(default=None, null=True, blank=True)

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
        """
        Returns best available display label.
        """
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
    # Permission helpers
    # =========================
    @property
    def can_manage_users(self) -> bool:
        """
        Admin + Manager may create/edit users (except only Admin can create Admin accounts).
        """
        return self.is_admin() or self.is_manager()

    @property
    def can_delete_users(self) -> bool:
        return self.is_admin()

    @property
    def can_create_projects(self) -> bool:
        return self.is_admin() or self.is_manager()

    @property
    def can_manage_projects(self) -> bool:
        return self.is_admin() or self.is_manager()

    @property
    def can_edit_self(self) -> bool:
        return True

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["date_joined"]


# ======================================================
# User Invite Token
# ======================================================
class UserInvite(models.Model):
    """
    One-time token allowing an invited user to set password & activate account.
    Typical flow:
      - Manager/Admin creates User (inactive, unusable password)
      - Create invite token → email it
      - User opens link, sets password → account becomes active → token deleted
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

    # Optional: expiration
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
        Static constructor — creates a new token for this user;
        replacing older one if necessary.
        """
        # ensure only one invite exists
        UserInvite.objects.filter(user=user).delete()

        token = get_random_string(56)
        expires = (
            timezone.now() + timezone.timedelta(days=validity_days)
            if validity_days else
            None
        )

        return UserInvite.objects.create(
            user=user,
            token=token,
            expires_at=expires,
        )

    def __str__(self) -> str:  # pragma: no cover
        return f"Invite<{self.user_id}>"
