# projects/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, DeleteView
from accounts.permissions import RequireManagerMixin
from .forms import ProjectForm, ProjectEditForm
from .models import Project

class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = "projects/project_list.html"
    context_object_name = "projects"

class ProjectCreateView(RequireManagerMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/project_form.html"
    success_url = reverse_lazy("projects:list")

    def form_valid(self, form):
        form.instance.manager = self.request.user
        return super().form_valid(form)

class ProjectUpdateView(RequireManagerMixin, UpdateView):
    model = Project
    form_class = ProjectEditForm
    template_name = "projects/project_edit.html"
    success_url = reverse_lazy("projects:list")

class ProjectDeleteView(RequireManagerMixin, DeleteView):
    model = Project
    template_name = "projects/project_confirm_delete.html"
    success_url = reverse_lazy("projects:list")
