from __future__ import annotations

from typing import Optional

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from projects.models import Project
from .models import Task, Label, TaskMember, TaskMessage, TaskCommit

User = get_user_model()


class TaskForm(forms.ModelForm):
    """
    Recebe `project` no __init__ para limitar assignee aos membros do projeto.
    Se `project` vier, filtramos assignees para (owner do projeto) ∪ (membros).
    """

    def __init__(self, *args, project: Optional[Project] = None, **kwargs):
        super().__init__(*args, **kwargs)

        # Estilização padrão (Bootstrap)
        for _, field in self.fields.items():
            if field.widget.__class__.__name__.lower().endswith("select"):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

        # Quando a view informa o projeto corrente, filtramos possíveis assignees
        if project is not None and "assignee" in self.fields:
            members = (
                User.objects.filter(
                    Q(project_memberships__project=project)
                    | Q(pk=project.owner_id)
                )
                .distinct()
                .order_by("username")
            )
            self.fields["assignee"].queryset = members

    class Meta:
        model = Task
        fields = [
            "project",
            "title",
            "key",
            "description",
            "status",
            "priority",
            "assignee",
            "labels",
            "due_date",
            "delivered_date",
            "attachment",
        ]
        widgets = {
            "description": forms.Textarea(
                attrs={"style": "height: 120px"}
            ),
        }


class LabelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _, field in self.fields.items():
            field.widget.attrs.setdefault("class", "form-control")

    class Meta:
        model = Label
        fields = ["name", "color"]


class TaskMemberForm(forms.ModelForm):
    """
    Recebe `task` para filtrar usuários já adicionados e limitar aos membros do projeto/owner.
    """

    def __init__(self, *args, task: Optional[Task] = None, **kwargs):
        super().__init__(*args, **kwargs)

        # Estilização
        for _, field in self.fields.items():
            if field.widget.__class__.__name__.lower().endswith("select"):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

        qs = User.objects.all()
        if task is not None:
            project = task.project
            base = (
                User.objects.filter(
                    Q(project_memberships__project=project)
                    | Q(pk=project.owner_id)
                )
                .exclude(task_memberships__task=task)
                .distinct()
                .order_by("username")
            )
            qs = base

        self.fields["user"].queryset = qs

    class Meta:
        model = TaskMember
        fields = ["user", "role"]


class TaskMessageForm(forms.ModelForm):
    """
    O `author_name` será preenchido automaticamente na view com o usuário atual.
    Aqui o form só lida com o texto.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _, field in self.fields.items():
            if field.widget.__class__.__name__.lower().endswith("select"):
                field.widget.attrs.setdefault("class", "form-select")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    class Meta:
        model = TaskMessage
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(attrs={"style": "height: 100px"}),
        }


class TaskCommitReviewForm(forms.ModelForm):
    """
    Formulário para o revisor preencher os campos de avaliação de IA e resolução da task.
    Usa os campos REAIS do model TaskCommit: `code_quality_text` e `resolution_text`.
    """

    code_quality_text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"style": "height: 90px", "class": "form-control"}
        ),
        help_text="Observações de qualidade do código (texto livre usado por IA).",
        label="Code quality (text)",
    )
    resolution_text = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"style": "height: 70px", "class": "form-control"}
        ),
        help_text="Explique o que este commit resolve na task.",
        label="What does this commit resolve?",
    )

    class Meta:
        model = TaskCommit
        fields = ["code_quality_text", "resolution_text", "processed"]


class KanbanFilterForm(forms.Form):
    """
    Filtro simples para o Kanban (texto livre).
    """
    q = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["q"].widget.attrs.setdefault(
            "class", "form-control form-control-sm"
        )
        self.fields["q"].widget.attrs.setdefault("placeholder", "Search…")
