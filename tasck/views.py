# tasck/views.py
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from projects.models import Project, ProjectMember
from .models import Task, TaskMember, TaskMessage
from .forms import TaskForm, TaskMemberForm, TaskMessageForm


# ========= helpers de permissão =========

def _user_display_name(user) -> str:
    # Usa a propriedade display_name do seu User customizado (accounts.User)
    # Se não existir, cai para get_username()
    return getattr(user, "display_name", None) or user.get_username()

def _user_is_project_member(user, project: Project) -> bool:
    if not user.is_authenticated:
        return False
    if project.owner_id == user.id:
        return True
    return ProjectMember.objects.filter(project=project, user=user).exists()

def _user_can_view_project(user, project: Project) -> bool:
    # Admin/manager sempre podem
    if getattr(user, "can_manage_projects", False):
        return True
    # Owner ou membro do projeto podem ver
    return _user_is_project_member(user, project)

def _user_can_edit_project(user, project: Project) -> bool:
    # Admin/manager ou owner do projeto
    if getattr(user, "can_manage_projects", False):
        return True
    return project.owner_id == user.id


# ========= Tasks =========

class TaskListView(LoginRequiredMixin, ListView):
    """
    Lista tasks apenas dos projetos aos quais o usuário tem acesso:
      - admin/manager: todas
      - demais: projetos onde é owner ou membro
    """
    model = Task
    template_name = "tasck/task_list.html"
    context_object_name = "tasks"
    paginate_by = 20

    def get_queryset(self):
        qs = (super().get_queryset()
              .select_related("project", "assignee", "reporter")
              .prefetch_related("labels"))
        user = self.request.user
        q = self.request.GET.get("q")

        if getattr(user, "can_manage_projects", False):
            # admin/manager vê tudo
            if q:
                qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(project__name__icontains=q))
            return qs.order_by("-created_at")

        # demais: somente tasks de projetos onde é owner ou membro
        qs = qs.filter(
            Q(project__owner=user) |
            Q(project__memberships__user=user)
        ).distinct()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(project__name__icontains=q))
        return qs.order_by("-created_at")


class TaskCreateView(LoginRequiredMixin, CreateView):
    """
    Criação de task:
      - Define reporter = usuário atual
      - Valida que o usuário tem acesso ao projeto selecionado
      - Fork do repo será tratado pelo signal após salvar
    """
    model = Task
    form_class = TaskForm
    template_name = "tasck/task_form.html"

    def dispatch(self, request, *args, **kwargs):
        # Se o form vier com project pré-selecionado por GET (?project=ID), validamos o acesso
        project_id = request.GET.get("project")
        if project_id:
            project = get_object_or_404(Project, pk=project_id)
            if not _user_can_view_project(request.user, project):
                raise PermissionDenied("You cannot create tasks in this project.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = self.request.user
        project = form.cleaned_data["project"]

        # valida acesso ao projeto
        if not _user_can_view_project(user, project):
            raise PermissionDenied("You cannot create tasks in this project.")

        form.instance.reporter = user
        resp = super().form_valid(form)
        messages.success(self.request, "Task created successfully.")
        return resp

    def get_success_url(self):
        return reverse("tasck:task_detail", kwargs={"pk": self.object.pk})


class TaskDetailView(LoginRequiredMixin, DetailView):
    """
    Detalhe de uma task + caixa de mensagens embutida (POST):
      - Apenas quem pode ver o projeto pode ver a task.
      - Post de mensagem preenche automaticamente author_name com o usuário atual.
    """
    model = Task
    template_name = "tasck/task_detail.html"
    context_object_name = "task"

    def get_queryset(self):
        qs = (super().get_queryset()
              .select_related("project", "assignee", "reporter")
              .prefetch_related("labels", "memberships__user", "messages"))
        user = self.request.user
        if getattr(user, "can_manage_projects", False):
            return qs
        # Restringe às tasks de projetos onde o user é owner/membro
        return qs.filter(
            Q(project__owner=user) |
            Q(project__memberships__user=user)
        ).distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Form de mensagem
        initial = {"author_name": _user_display_name(self.request.user)}
        ctx["message_form"] = TaskMessageForm(initial=initial)
        # Lista de mensagens (já vem no prefetch), mas vamos ordenar na view para garantir
        ctx["messages_list"] = self.object.messages.select_related(None).order_by("created_at", "pk")
        return ctx

    def post(self, request, *args, **kwargs):
        """
        Recebe a postagem de mensagem (campo 'text' e opcionalmente 'author_name').
        """
        self.object = self.get_object()
        user = request.user

        # Checa se pode interagir
        if not _user_can_view_project(user, self.object.project):
            raise PermissionDenied("You cannot post messages in this task.")

        form = TaskMessageForm(request.POST)
        if form.is_valid():
            msg: TaskMessage = form.save(commit=False)
            msg.task = self.object
            msg.agent = TaskMessage.Agent.USER

            # Preenche/força o author_name automaticamente com o usuário atual,
            # porém se você quiser permitir edição manual, comente a linha abaixo.
            msg.author_name = _user_display_name(user)

            msg.save()
            messages.success(request, "Message posted.")
            return redirect("tasck:task_detail", pk=self.object.pk)

        # re-render com erros
        ctx = self.get_context_data(object=self.object)
        ctx["message_form"] = form
        return self.render_to_response(ctx)


class TaskUpdateView(LoginRequiredMixin, UpdateView):
    """
    Edição de task:
      - Admin/manager ou owner do projeto podem editar qualquer task do projeto.
      - Reporter também pode editar por padrão? (ajuste conforme sua regra)
    """
    model = Task
    form_class = TaskForm
    template_name = "tasck/task_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not (_user_can_edit_project(request.user, self.object.project) or self.object.reporter_id == request.user.id):
            raise PermissionDenied("You cannot edit this task.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Task updated successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("tasck:task_detail", kwargs={"pk": self.object.pk})


class TaskDeleteView(LoginRequiredMixin, DeleteView):
    """
    Remoção de task:
      - Admin/manager ou owner do projeto podem remover.
    """
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


# ========= Membros da Task =========

class TaskMembersView(LoginRequiredMixin, View):
    """
    Tela para gerenciar membros da task (adicionar/remover).
    - Apenas admin/manager ou owner do projeto podem gerenciar membros.
    """
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

        form = TaskMemberForm()
        memberships = task.memberships.select_related("user").all()
        return render(request, self.template_name, {"task": task, "form": form, "memberships": memberships})

    def post(self, request, pk):
        task = self._get_task(pk)
        if not _user_can_edit_project(request.user, task.project):
            raise PermissionDenied("You cannot manage members for this task.")

        form = TaskMemberForm(request.POST)
        if form.is_valid():
            member = form.save(commit=False)
            member.task = task
            # Evita duplicidade
            exists = TaskMember.objects.filter(task=task, user=member.user).exists()
            if exists:
                messages.warning(request, "This user is already a member of the task.")
            else:
                member.save()
                messages.success(request, "Member added to task.")
            return redirect("tasck:task_members", pk=task.pk)

        memberships = task.memberships.select_related("user").all()
        return render(request, self.template_name, {"task": task, "form": form, "memberships": memberships})


class TaskMemberDeleteView(LoginRequiredMixin, View):
    """
    Remoção de um membro específico da task.
    """
    def post(self, request, pk, user_id):
        task = get_object_or_404(Task.objects.select_related("project"), pk=pk)
        if not _user_can_edit_project(request.user, task.project):
            raise PermissionDenied("You cannot manage members for this task.")

        TaskMember.objects.filter(task=task, user_id=user_id).delete()
        messages.success(request, "Member removed from task.")
        return redirect("tasck:task_members", pk=task.pk)
