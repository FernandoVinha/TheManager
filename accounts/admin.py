from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    list_display = (
        "email",
        "is_system_manager", "is_employee", "is_client",
        "is_active", "is_staff", "is_superuser",
        "date_joined",
    )
    list_filter = (
        "is_system_manager", "is_employee", "is_client",
        "is_active", "is_staff", "is_superuser",
    )
    search_fields = ("email",)
    ordering = ("email",)

    fieldsets = (
        ("Credenciais", {"fields": ("email", "password")}),
        ("Papeis no sistema", {"fields": ("is_system_manager", "is_employee", "is_client")}),
        ("Perfil", {"fields": ("avatar", "hourly_rate")}),
        ("Permissões Django", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        ("Novo usuário", {
            "classes": ("wide",),
            "fields": (
                "email", "password1", "password2",
                "is_system_manager", "is_employee", "is_client",
                "avatar", "hourly_rate",
                "is_active", "is_staff", "is_superuser",
            ),
        }),
    )
