# projects/forms.py
from __future__ import annotations
from django import forms
from django.contrib.auth import get_user_model
from .models import ProjectMember, Project

User = get_user_model()

class ProjectForm(forms.ModelForm):
    class Meta:
        from .models import Project  # se já existir no arquivo, remova esta linha
        model = Project
        fields = [
            "name", "key", "methodology", "description", "image",
            "repo_owner", "repo_name", "visibility", "default_branch",
            "auto_init", "gitea_repo_url",
            "sprint_length_days", "wip_limit", "xp_pair_programming",
        ]
        widgets = {
            "gitea_repo_url": forms.URLInput(attrs={"readonly": "readonly"}),
        }

class ProjectMemberForm(forms.ModelForm):
    """
    Recebe `project` no __init__ para:
      - Remover usuários já membros
      - (Opcional) aplicar qualquer regra extra de filtro
    """
    def __init__(self, *args, project: Project | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = User.objects.all()
        if project is not None:
            qs = qs.exclude(project_memberships__project=project)
        self.fields["user"].queryset = qs.order_by("username")

    class Meta:
        model = ProjectMember
        fields = ["user", "role"]
