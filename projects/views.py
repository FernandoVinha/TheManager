# projects/views.py

from __future__ import annotations

import logging
from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, DetailView

from tasck.models import Task

from .forms import ProjectForm, ProjectMemberForm
from .models import Project, ProjectMember

log = logging.getLogger(__name__)


# ---------- Permissão: criar -----------
class CanCreateProjectsRequiredMixin:
    """
    Permite apenas superuser/Admin/Manager (via user.can_create_projects)
    criar novos projetos.
    """
    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated or not getattr(user, "can_create_projects", False):
            raise PermissionDenied("Você não tem permissão para criar projetos.")
        return super().dispatch(request, *args, **kwargs)


# ---------- Permissão: gerenciar (editar/deletar/gerenciar membros) -----------
class CanManageProjectsRequiredMixin:
    """
    Regra de permissão para views que alteram projetos (update/delete/membros):

    - Superuser/Admin/Manager (user.can_manage_projects == True) podem
      gerenciar qualquer projeto.
    - O OWNER do projeto também pode gerenciar aquele projeto específico,
      mesmo que não seja admin/manager.
    """
    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            raise PermissionDenied("Você não tem permissão para gerenciar projetos.")

        # Admin/Manager/superuser: usam o helper global
        if getattr(user, "can_manage_projects", False):
            return super().dispatch(request, *args, **kwargs)

        # Senão, tenta checar se o usuário é owner do projeto
        project_pk = kwargs.get("pk") or request.GET.get("project_id")
        if project_pk:
            try:
                project = Project.objects.only("owner_id").get(pk=project_pk)
            except Project.DoesNotExist as exc:
                # Se o projeto não existe, melhor retornar 404 do que estourar DoesNotExist
                raise Http404("Projeto não encontrado.") from exc

            if project.owner_id == user.id:
                # Opcional: expõe project para outras partes da view, se quiser
                setattr(self, "_permission_checked_project", project)
                return super().dispatch(request, *args, **kwargs)

        raise PermissionDenied("Você não tem permissão para gerenciar este projeto.")


# ---------- LIST ----------
class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = "projects/project_list.html"
    context_object_name = "projects"
    paginate_by = 20

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("owner")
            .prefetch_related("memberships__user")
        )

        q = self.request.GET.get("q")
        user = self.request.user

        if getattr(user, "can_manage_projects", False):
            # Admin/Manager veem TODOS os projetos
            base = qs
        else:
            # Outros: apenas projetos em que é owner OU membro
            base = qs.filter(
                Q(owner=user) |
                Q(memberships__user=user)
            ).distinct()

        if q:
            base = base.filter(
                Q(name__icontains=q) |
                Q(description__icontains=q) |
                Q(key__icontains=q)
            )

        return base.order_by("-created_at")


# ---------- CREATE ----------
class ProjectCreateView(LoginRequiredMixin, CanCreateProjectsRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/project_form.html"
    success_url = reverse_lazy("projects:project_list")

    @transaction.atomic
    def form_valid(self, form):
        form.instance.owner = self.request.user
        if not form.instance.repo_name:
            form.instance.repo_name = form.instance.name

        resp = super().form_valid(form)

        # Fallback: garante membership do criador como OWNER
        ProjectMember.objects.get_or_create(
            project=self.object,
            user=self.request.user,
            defaults={"role": ProjectMember.Role.OWNER},
        )
        messages.success(self.request, "Projeto criado com sucesso.")
        return resp


# ---------- UPDATE ----------
class ProjectUpdateView(LoginRequiredMixin, CanManageProjectsRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/project_form.html"
    success_url = reverse_lazy("projects:project_list")

    def form_valid(self, form):
        if not form.instance.repo_name:
            form.instance.repo_name = form.instance.name
        messages.success(self.request, "Projeto atualizado com sucesso.")
        return super().form_valid(form)


# ---------- DELETE ----------
class ProjectDeleteView(LoginRequiredMixin, CanManageProjectsRequiredMixin, DeleteView):
    model = Project
    template_name = "projects/project_confirm_delete.html"
    success_url = reverse_lazy("projects:project_list")

    def post(self, request, *args, **kwargs):
        """
        Trata o caso em que o projeto já foi removido ou algo relacionado
        dispara DoesNotExist/404 durante o processo.
        """
        try:
            return super().post(request, *args, **kwargs)
        except (Http404, Project.DoesNotExist, ObjectDoesNotExist):
            messages.info(self.request, "Este projeto já foi removido ou não existe.")
            return redirect("projects:project_list")

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Projeto deletado com sucesso.")
        return super().delete(request, *args, **kwargs)


# ---------- MEMBERS ----------
class ProjectMembersView(LoginRequiredMixin, CanManageProjectsRequiredMixin, View):
    """
    Admin/Manager podem gerenciar membros de qualquer projeto.
    O OWNER do projeto também pode gerenciar os membros do seu projeto.
    """
    template_name = "projects/project_members.html"

    def get_project(self, pk: int) -> Project:
        return get_object_or_404(Project, pk=pk)

    def get(self, request, pk: int):
        project = self.get_project(pk)
        form = ProjectMemberForm(project=project)
        members = (
            ProjectMember.objects
            .filter(project=project)
            .select_related("user")
            .order_by("user__username")
        )
        return render(
            request,
            self.template_name,
            {"project": project, "form": form, "members": members},
        )

    def post(self, request, pk: int):
        project = self.get_project(pk)
        form = ProjectMemberForm(request.POST, project=project)

        if form.is_valid():
            member = form.save(commit=False)
            member.project = project

            if ProjectMember.objects.filter(project=project, user=member.user).exists():
                messages.info(request, "Usuário já é membro do projeto.")
            else:
                member.save()  # signal adiciona colaborador no Gitea
                messages.success(request, "Membro adicionado com sucesso.")

            return redirect("projects:project_members", pk=project.pk)

        members = (
            ProjectMember.objects
            .filter(project=project)
            .select_related("user")
            .order_by("user__username")
        )
        return render(
            request,
            self.template_name,
            {"project": project, "form": form, "members": members},
        )


# ---------- DETAIL / BOARD ----------
class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = "projects/project_detail.html"
    context_object_name = "project"

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("owner")
            .prefetch_related("memberships__user")
        )
        user = self.request.user

        if getattr(user, "can_manage_projects", False):
            # Admin/Manager/Superuser enxergam todos
            return qs

        # Usuário comum: somente owner ou membro
        return qs.filter(
            Q(owner=user) |
            Q(memberships__user=user)
        ).distinct()

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        project: Project = self.object

        # Filtro rápido por texto
        q = (self.request.GET.get("q") or "").strip()
        qs = (
            Task.objects.filter(project=project)
            .select_related("assignee", "reporter")
            .prefetch_related("labels")
        )

        if q:
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(description__icontains=q) |
                Q(key__icontains=q)
            )

        # Mapeia status -> rótulo legível
        status_map = {
            Task.Status.TODO: "To do",
            Task.Status.IN_PROGRESS: "In progress",
            Task.Status.REVIEW: "In review",
            Task.Status.VERIFIED: "Verified",
            Task.Status.DONE: "Done",
            Task.Status.FAILED: "Failed",
        }

        # Cria dicionário de colunas já com as chaves na ordem desejada
        columns: dict[str, list[Task]] = {label: [] for label in status_map.values()}

        # Preenche colunas (ordenando por criação desc)
        for t in qs.order_by("-created_at"):
            label = status_map.get(t.status, status_map[Task.Status.TODO])
            columns[label].append(t)

        ctx["columns"] = columns
        ctx["tasks_count"] = qs.count()
        ctx["query"] = q
        return ctx
