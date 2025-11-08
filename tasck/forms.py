from __future__ import annotations
from django import forms
from django.contrib.auth import get_user_model
from .models import Task, Label, TaskMember
from projects.models import Project

User = get_user_model()

class TaskForm(forms.ModelForm):
    """
    Recebe project no __init__ para limitar assignee aos membros do projeto.
    """
    def __init__(self, *args, project: Project | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if project is not None:
            members = User.objects.filter(project_memberships__project=project).distinct()
            members = members.union(User.objects.filter(pk=project.owner_id))
            self.fields["assignee"].queryset = members.order_by("username")

    class Meta:
        model = Task
        fields = [
            "title", "key", "description", "status", "priority",
            "assignee", "labels",
            "due_date", "delivered_date",
            "attachment",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"style": "height: 120px"}),
        }

class LabelForm(forms.ModelForm):
    class Meta:
        model = Label
        fields = ["name", "color"]

class TaskMemberForm(forms.ModelForm):
    """
    Recebe `task` para filtrar usuários já adicionados e limitar aos membros do projeto/owner.
    """
    def __init__(self, *args, task: Task | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = User.objects.all()
        if task is not None:
            project = task.project
            base = User.objects.filter(project_memberships__project=project).distinct()
            base = base.union(User.objects.filter(pk=project.owner_id))
            # remove os que já são membros
            base = base.exclude(task_memberships__task=task)
            qs = base
        self.fields["user"].queryset = qs.order_by("username")

    class Meta:
        model = TaskMember
        fields = ["user", "role"]
