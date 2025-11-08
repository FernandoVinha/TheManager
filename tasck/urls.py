# tasck/urls.py
from django.urls import path

from . import views

app_name = "tasck"

urlpatterns = [

    # LIST + CREATE
    path("", views.TaskListView.as_view(), name="task_list"),
    path("new/", views.TaskCreateView.as_view(), name="task_create"),

    # DETAIL
    path("<int:pk>/", views.TaskDetailView.as_view(), name="task_detail"),

    # EDIT
    path("<int:pk>/edit/", views.TaskUpdateView.as_view(), name="task_edit"),

    # DELETE
    path("<int:pk>/delete/", views.TaskDeleteView.as_view(), name="task_delete"),

    # MEMBERS LIST + ADD
    path("<int:pk>/members/", views.TaskMembersView.as_view(), name="task_members"),

    # REMOVE MEMBER
    path("<int:pk>/members/<int:user_id>/delete/", views.TaskMemberDeleteView.as_view(), name="task_member_delete"),
]
