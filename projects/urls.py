# projects/urls.py
from django.urls import path
from .views import (
    ProjectListView,
    ProjectCreateView,
    ProjectUpdateView,
    ProjectDeleteView,
    ProjectMembersView,
    ProjectDetailView,
)

app_name = "projects"

urlpatterns = [
    path("", ProjectListView.as_view(), name="project_list"),
    path("new/", ProjectCreateView.as_view(), name="project_create"),
    path("<int:pk>/", ProjectDetailView.as_view(), name="project_detail"),
    path("<int:pk>/edit/", ProjectUpdateView.as_view(), name="project_edit"),
    path("<int:pk>/delete/", ProjectDeleteView.as_view(), name="project_delete"),
    path("<int:pk>/members/", ProjectMembersView.as_view(), name="project_members"),
]
