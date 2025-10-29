# projects/urls.py
from django.urls import path
from .views import ProjectListView, ProjectCreateView, ProjectUpdateView, ProjectDeleteView

app_name = "projects"  # <<<<<< ESSENCIAL

urlpatterns = [
    path("", ProjectListView.as_view(), name="list"),
    path("new/", ProjectCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", ProjectUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", ProjectDeleteView.as_view(), name="delete"),
]
