from __future__ import annotations
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView
from .models import Project, ProjectMember
from .forms import ProjectForm, ProjectMemberForm

class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = "projects/project_list.html"
    context_object_name = "projects"
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related("owner")
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(name__icontains=q)
        return qs.order_by("-created_at")

class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/project_form.html"
    success_url = reverse_lazy("project_list")

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

class ProjectMembersView(LoginRequiredMixin, View):
    template_name = "projects/project_members.html"

    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        form = ProjectMemberForm()
        return render(request, self.template_name, {"project": project, "form": form})

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        form = ProjectMemberForm(request.POST)
        if form.is_valid():
            member = form.save(commit=False)
            member.project = project
            member.save()  # signals will handle Gitea collaborator add
            return redirect("project_members", pk=project.pk)
        return render(request, self.template_name, {"project": project, "form": form})
