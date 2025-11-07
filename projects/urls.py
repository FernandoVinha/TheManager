from django.urls import path
from .views import ProjectListView, ProjectCreateView, ProjectMembersView

urlpatterns = [
    path("", ProjectListView.as_view(), name="project_list"),
    path("new/", ProjectCreateView.as_view(), name="project_create"),
    path("<int:pk>/members/", ProjectMembersView.as_view(), name="project_members"),
]
