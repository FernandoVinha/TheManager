"""
Context processor que expõe atalho `U` nos templates para o usuário atual.
"""

from typing import Any, Dict, Optional

from django.http import HttpRequest


def user_role_context(request: HttpRequest) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Torna o perfil do usuário + permissões disponíveis para todos os templates
    como `U`. Se o usuário não estiver autenticado, `U` será None.

    Exemplo de uso no template:
      {% if U and U.can_manage_users %} ... {% endif %}
    """
    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return {"U": None}

    U: Dict[str, Any] = {
        # Basic identity
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.get_full_name() or user.username,

        # Gitea info
        "gitea_id": user.gitea_id,
        "gitea_avatar_url": user.gitea_avatar_url,
        "gitea_url": user.gitea_url,
        "gitea_full_name": user.gitea_full_name,
        "gitea_website": user.gitea_website,
        "gitea_location": user.gitea_location,
        "gitea_description": user.gitea_description,

        # Gitea preferences
        "gitea_visibility": user.gitea_visibility,
        "gitea_max_repo_creation": user.gitea_max_repo_creation,
        "gitea_allow_create_organization": user.gitea_allow_create_organization,
        "gitea_allow_git_hook": user.gitea_allow_git_hook,
        "gitea_allow_import_local": user.gitea_allow_import_local,
        "gitea_restricted": user.gitea_restricted,
        "gitea_prohibit_login": user.gitea_prohibit_login,

        # Role
        "role": user.role,
        "is_admin": user.is_admin(),
        "is_manager": user.is_manager(),
        "is_senior": user.is_senior(),
        "is_regular": user.is_regular(),
        "is_junior": user.is_junior(),

        # Permission shortcuts
        "can_manage_users": user.can_manage_users,
        "can_delete_users": user.can_delete_users,
        "can_create_projects": user.can_create_projects,
        "can_manage_projects": user.can_manage_projects,

        # Useful timestamps
        "date_joined": user.date_joined,
        "last_login": user.last_login,
        "password_updated_at": user.password_updated_at,
    }

    return {"U": U}
