from __future__ import annotations
from django import forms
from django.contrib.auth import get_user_model
from .models import Project, ProjectMember

User = get_user_model()

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = (
            "name", "key", "methodology", "description",
            "repo_owner", "repo_name", "visibility", "default_branch", "auto_init",
            "sprint_length_days", "wip_limit", "xp_pair_programming",
        )

class ProjectMemberForm(forms.ModelForm):
    user = forms.ModelChoiceField(queryset=User.objects.all())

    class Meta:
        model = ProjectMember
        fields = ("user", "role")
