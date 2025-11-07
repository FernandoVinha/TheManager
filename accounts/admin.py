# accounts/admin.py
from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User
from .services import gitea as gitea_api


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """
    Admin do usuário customizado:
      - Sem duplicar username/email/admin (usamos campos nativos do Django)
      - Grupo "Gitea" com preferências/limites/metadata e campos somente leitura
      - Ação para sincronizar PATCH no Gitea manualmente
    """

    # colunas da listagem
    list_display = (
        "username",
        "email",
        "is_superuser",
        "is_staff",
        "is_active",
        "gitea_id",
        "gitea_max_repo_creation",
        "last_login",
        "date_joined",
    )
    list_filter = ("is_superuser", "is_staff", "is_active", "gitea_visibility")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)

    # somente leitura — dados que vêm do Gitea / sistema
    readonly_fields = ("gitea_id", "gitea_avatar_url", "gitea_url", "password_updated_at")

    # fieldsets (edição)
    fieldsets = (
        (_("Credenciais"), {"fields": ("username", "password")}),
        (_("Informações pessoais"), {"fields": ("first_name", "last_name", "email")}),
        (_("Permissões"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Datas importantes"), {"fields": ("last_login", "date_joined")}),
        (_("Gitea — preferências e limites"),
         {"fields": (
             "gitea_max_repo_creation",
             "gitea_visibility",
             "gitea_allow_create_organization",
             "gitea_allow_git_hook",
             "gitea_allow_import_local",
             "gitea_restricted",
             "gitea_prohibit_login",
             "gitea_full_name",
             "gitea_website",
             "gitea_location",
             "gitea_description",
         )}),
        (_("Gitea — somente leitura"),
         {"fields": ("gitea_id", "gitea_avatar_url", "gitea_url", "password_updated_at")}),
    )

    # fieldsets (criação)
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username",
                "email",
                "password1",
                "password2",
                # flags principais já na criação (Django)
                "is_superuser",
                "is_staff",
                "is_active",
                # preferências iniciais do Gitea (opcionais)
                "gitea_max_repo_creation",
                "gitea_visibility",
                "gitea_allow_create_organization",
                "gitea_restricted",
                "gitea_prohibit_login",
                "gitea_full_name",
                "gitea_website",
                "gitea_location",
                "gitea_description",
            ),
        }),
    )

    actions = ("action_sync_gitea_patch",)

    @admin.action(description="Sincronizar no Gitea (PATCH)")
    def action_sync_gitea_patch(self, request, queryset):
        """
        Aplica PATCH no Gitea para cada usuário selecionado, empurrando:
          - email  (sempre = Django)
          - admin  (espelha is_superuser)
          - max_repo_creation / visibility / metadata se definidos
        *Não* troca senha (isso é feito automaticamente se GITEA_SYNC_PASSWORD=True e set_password() for chamado).
        """
        ok, fail = 0, 0
        for user in queryset:
            try:
                payload = {
                    "email": user.email,
                    "is_admin": bool(user.is_superuser),
                }
                if user.gitea_max_repo_creation is not None:
                    payload["max_repo_creation"] = int(user.gitea_max_repo_creation)
                if user.gitea_visibility:
                    payload["visibility"] = user.gitea_visibility
                if user.gitea_full_name or user.get_full_name():
                    payload["full_name"] = user.gitea_full_name or user.get_full_name()
                if user.gitea_website:
                    payload["website"] = user.gitea_website
                if user.gitea_location:
                    payload["location"] = user.gitea_location
                if user.gitea_description:
                    payload["description"] = user.gitea_description

                gitea_api.patch_user(username=user.username, **payload)
                ok += 1
            except Exception as e:
                fail += 1
        self.message_user(request, f"PATCH no Gitea concluído: {ok} ok, {fail} falha(s).")
