from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
)

from projects.models import Project, ProjectMember
from .models import Task, TaskMember, TaskMessage, Label
from .forms import (
    TaskForm,
    TaskMemberForm,
    TaskMessageForm,
    KanbanFilterForm,
)


# =========================
# Helpers de permissão
# =========================

def _user_display_name(user) -> str:
    return getattr(user, "display_name", None) or user.get_username()


def _user_is_project_member(user, project: Project) -> bool:
    if not user.is_authenticated:
        return False
    if project.owner_id == user.id:
        return True
    return ProjectMember.objects.filter(project=project, user=user).exists()


def _user_can_view_project(user, project: Project) -> bool:
    if getattr(user, "can_manage_projects", False):
        return True
    return _user_is_project_member(user, project)


def _user_can_edit_project(user, project: Project) -> bool:
    if getattr(user, "can_manage_projects", False):
        return True
    return project.owner_id == user.id


# =========================
# Tasks — CRUD + listagem
# =========================

class TaskListView(LoginRequiredMixin, ListView):
    model = Task
    template_name = "tasck/task_list.html"
    context_object_name = "tasks"
    paginate_by = 20

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("project", "assignee", "reporter")
            .prefetch_related("labels")
        )
        user = self.request.user
        q = self.request.GET.get("q")

        # Admin global de projetos
        if getattr(user, "can_manage_projects", False):
            if q:
                qs = qs.filter(
                    Q(title__icontains=q)
                    | Q(description__icontains=q)
                    | Q(project__name__icontains=q)
                    | Q(key__icontains=q)
                )
            return qs.order_by("-created_at")

        # Usuário normal: só vê tasks de projetos onde é owner ou membro
        qs = qs.filter(
            Q(project__owner=user) | Q(project__memberships__user=user)
        ).distinct()
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(project__name__icontains=q)
                | Q(key__icontains=q)
            )
        return qs.order_by("-created_at")


class TaskCreateView(LoginRequiredMixin, CreateView):
    model = Task
    form_class = TaskForm
    template_name = "tasck/task_form.html"

    def dispatch(self, request, *args, **kwargs):
        """
        Se vier ?project=ID, valida permissão e fixa o projeto.
        """
        self.fixed_project: Project | None = None
        project_id = request.GET.get("project")
        if project_id:
            project = get_object_or_404(Project, pk=project_id)
            if not _user_can_view_project(request.user, project):
                raise PermissionDenied("You cannot create tasks in this project.")
            self.fixed_project = project
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        if self.fixed_project:
            initial["project"] = self.fixed_project.pk
        return initial

    def get_form_kwargs(self):
        """
        Passa o project para o form (para filtrar assignee aos membros).
        """
        kwargs = super().get_form_kwargs()
        instance = kwargs.get("instance")
        project = self.fixed_project or (instance.project if instance else None)
        kwargs["project"] = project
        return kwargs

    def get_form(self, form_class=None):
        """
        Se o projeto está fixado: esconde o campo 'project' e limita o queryset a ele.
        """
        form = super().get_form(form_class)
        if self.fixed_project:
            from django import forms as djforms

            form.fields["project"].queryset = Project.objects.filter(
                pk=self.fixed_project.pk
            )
            form.fields["project"].initial = self.fixed_project.pk
            form.fields["project"].widget = djforms.HiddenInput()
        return form

    def form_valid(self, form):
        """
        Garante que o projeto é o fixado, mesmo que alguém tente adulterar o POST.
        """
        if self.fixed_project:
            form.instance.project = self.fixed_project
        form.instance.reporter = self.request.user
        resp = super().form_valid(form)
        messages.success(self.request, "Task created successfully.")
        return resp

    def get_success_url(self):
        return reverse("tasck:task_detail", kwargs={"pk": self.object.pk})


class TaskDetailView(LoginRequiredMixin, DetailView):
    model = Task
    template_name = "tasck/task_detail.html"
    context_object_name = "task"

    def get_queryset(self):
        qs = (
            super()
            .get_queryset()
            .select_related("project", "assignee", "reporter")
            .prefetch_related("labels", "memberships__user", "messages")
        )
        user = self.request.user
        if getattr(user, "can_manage_projects", False):
            return qs
        return qs.filter(
            Q(project__owner=user) | Q(project__memberships__user=user)
        ).distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["message_form"] = TaskMessageForm()
        ctx["messages_list"] = self.object.messages.order_by("created_at", "pk")
        return ctx

    def post(self, request, *args, **kwargs):
        """
        Post de mensagem (texto). author_name é preenchido automaticamente.
        """
        self.object = self.get_object()
        user = request.user

        if not _user_can_view_project(user, self.object.project):
            raise PermissionDenied("You cannot post messages in this task.")

        form = TaskMessageForm(request.POST)
        if form.is_valid():
            msg: TaskMessage = form.save(commit=False)
            msg.task = self.object
            msg.agent = TaskMessage.Agent.USER
            msg.author_name = _user_display_name(user)
            msg.save()
            messages.success(request, "Message posted.")
            return redirect("tasck:task_detail", pk=self.object.pk)

        ctx = self.get_context_data(object=self.object)
        ctx["message_form"] = form
        return self.render_to_response(ctx)


class TaskUpdateView(LoginRequiredMixin, UpdateView):
    model = Task
    form_class = TaskForm
    template_name = "tasck/task_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not (
            _user_can_edit_project(request.user, self.object.project)
            or self.object.reporter_id == request.user.id
        ):
            raise PermissionDenied("You cannot edit this task.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        """
        Passa o project atual para o form (para filtrar assignee).
        """
        kwargs = super().get_form_kwargs()
        kwargs["project"] = self.object.project
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Task updated successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("tasck:task_detail", kwargs={"pk": self.object.pk})


class TaskDeleteView(LoginRequiredMixin, DeleteView):
    model = Task
    template_name = "tasck/task_confirm_delete.html"
    success_url = reverse_lazy("tasck:task_list")

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not _user_can_edit_project(request.user, self.object.project):
            raise PermissionDenied("You cannot delete this task.")
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Task deleted.")
        return super().delete(request, *args, **kwargs)


class TaskMembersView(LoginRequiredMixin, View):
    template_name = "tasck/task_members.html"

    def _get_task(self, pk: int) -> Task:
        task = get_object_or_404(Task.objects.select_related("project"), pk=pk)
        if not _user_can_view_project(self.request.user, task.project):
            raise PermissionDenied("You cannot view members for this task.")
        return task

    def get(self, request, pk):
        task = self._get_task(pk)
        if not _user_can_edit_project(request.user, task.project):
            raise PermissionDenied("You cannot manage members for this task.")
        # usa o task para filtrar possíveis usuários
        form = TaskMemberForm(task=task)
        memberships = task.memberships.select_related("user").all()
        return render(
            request,
            self.template_name,
            {"task": task, "form": form, "memberships": memberships},
        )

    def post(self, request, pk):
        task = self._get_task(pk)
        if not _user_can_edit_project(request.user, task.project):
            raise PermissionDenied("You cannot manage members for this task.")

        form = TaskMemberForm(request.POST, task=task)
        if form.is_valid():
            member = form.save(commit=False)
            member.task = task
            exists = TaskMember.objects.filter(task=task, user=member.user).exists()
            if exists:
                messages.warning(
                    request, "This user is already a member of the task."
                )
            else:
                member.save()
                messages.success(request, "Member added to task.")
            return redirect("tasck:task_members", pk=task.pk)

        memberships = task.memberships.select_related("user").all()
        return render(
            request,
            self.template_name,
            {"task": task, "form": form, "memberships": memberships},
        )


class TaskMemberDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, user_id):
        task = get_object_or_404(Task.objects.select_related("project"), pk=pk)
        if not _user_can_edit_project(request.user, task.project):
            raise PermissionDenied("You cannot manage members for this task.")
        TaskMember.objects.filter(task=task, user_id=user_id).delete()
        messages.success(request, "Member removed from task.")
        return redirect("tasck:task_members", pk=task.pk)


# =========================
# Kanban
# =========================

class ProjectKanbanView(LoginRequiredMixin, View):
    template_name = "tasck/kanban.html"

    def get(self, request: HttpRequest, project_id: int) -> HttpResponse:
        project = get_object_or_404(Project, pk=project_id)
        if not _user_can_view_project(request.user, project):
            raise PermissionDenied()

        form = KanbanFilterForm(request.GET or None)
        q = form.cleaned_data.get("q") if form.is_valid() else ""

        qs = (
            Task.objects.filter(project=project)
            .select_related("assignee", "reporter")
            .prefetch_related("labels")
        )
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(key__icontains=q)
            )

        # Dicionário de colunas: status -> lista de tasks
        columns = {
            Task.Status.TODO: [],
            Task.Status.IN_PROGRESS: [],
            Task.Status.REVIEW: [],
            Task.Status.VERIFIED: [],
            Task.Status.DONE: [],
            Task.Status.FAILED: [],
        }
        for t in qs.order_by("-created_at"):
            columns.get(t.status, columns[Task.Status.TODO]).append(t)

        ctx = {"project": project, "columns": columns, "form": form}
        return render(request, self.template_name, ctx)


class KanbanStatusUpdateView(LoginRequiredMixin, View):
    """
    Atualização de status usada pelo drag & drop do Kanban.
    URL: /projects/<project_id>/kanban/status/<task_id>/
    Método: POST, campo "status"
    """

    def post(self, request: HttpRequest, project_id: int, task_id: int) -> JsonResponse:
        project = get_object_or_404(Project, pk=project_id)
        task = get_object_or_404(Task, pk=task_id, project=project)

        if not _user_can_edit_project(request.user, project) and task.reporter_id != request.user.id:
            raise PermissionDenied("You cannot move this task.")

        new_status = (request.POST.get("status") or "").strip()
        valid = {k for k, _ in Task.Status.choices}
        if new_status not in valid:
            return JsonResponse({"ok": False, "error": "Invalid status"}, status=400)

        task.status = new_status
        task.save(update_fields=["status"])
        return JsonResponse({"ok": True})


class ProjectTaskListView(LoginRequiredMixin, View):
    template_name = "tasck/task_list_project.html"

    def get(self, request, project_id: int):
        project = get_object_or_404(Project, pk=project_id)
        if not _user_can_view_project(request.user, project):
            raise PermissionDenied()

        form = KanbanFilterForm(request.GET or None)
        q = form.cleaned_data.get("q") if form.is_valid() else ""

        qs = (
            Task.objects.filter(project=project)
            .select_related("assignee", "reporter")
            .prefetch_related("labels")
        )
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(key__icontains=q)
            )

        tasks = qs.order_by("-created_at")
        return render(
            request,
            self.template_name,
            {"project": project, "tasks": tasks, "form": form},
        )


# =========================
# Labels — AJAX create
# =========================

class LabelCreateAjaxView(LoginRequiredMixin, View):
    """
    Cria Label via AJAX.
    POST: name, color (#rrggbb opcional)
    """

    def post(self, request):
        name = (request.POST.get("name") or "").strip()
        color = (request.POST.get("color") or "#6b4ce6").strip() or "#6b4ce6"
        if not name:
            return JsonResponse(
                {"ok": False, "error": "Name is required"}, status=400
            )

        # Nome é único; se a label já existir, atualiza a cor (se diferente)
        label, created = Label.objects.get_or_create(
            name=name,
            defaults={"color": color},
        )
        if not created and label.color != color and color:
            label.color = color
            label.save(update_fields=["color"])

        return JsonResponse(
            {
                "ok": True,
                "id": label.id,
                "name": label.name,
                "color": label.color,
                "created": created,
            }
        )
