from django.urls import path
from .views import (
    TaskListView,
    TaskCreateView,
    TaskDetailView,
    TaskUpdateView,
    TaskDeleteView,
    TaskMembersView,
    TaskMemberDeleteView,
    ProjectKanbanView,
    KanbanStatusUpdateView,
    ProjectTaskListView,
    LabelCreateAjaxView,
)

app_name = "tasck"

urlpatterns = [
    path("tasks/", TaskListView.as_view(), name="task_list"),
    path("tasks/new/", TaskCreateView.as_view(), name="task_create"),
    path("tasks/<int:pk>/", TaskDetailView.as_view(), name="task_detail"),
    path("tasks/<int:pk>/edit/", TaskUpdateView.as_view(), name="task_update"),
    path("tasks/<int:pk>/delete/", TaskDeleteView.as_view(), name="task_delete"),

    path("tasks/<int:pk>/members/", TaskMembersView.as_view(), name="task_members"),
    path("tasks/<int:pk>/members/<int:user_id>/delete/", TaskMemberDeleteView.as_view(), name="task_member_delete"),

    # Kanban por projeto
    path("projects/<int:project_id>/kanban/", ProjectKanbanView.as_view(), name="project_kanban"),
    path("projects/<int:project_id>/kanban/status/<int:task_id>/", KanbanStatusUpdateView.as_view(), name="kanban_status_update"),

    path("projects/<int:project_id>/tasks/", ProjectTaskListView.as_view(), name="project_task_list"),


    path("labels/ajax/create/", LabelCreateAjaxView.as_view(), name="label_create_ajax"),
]
