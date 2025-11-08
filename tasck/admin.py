from django.contrib import admin
from .models import Task, Label, TaskMember

@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ("name", "color")
    search_fields = ("name",)

class TaskMemberInline(admin.TabularInline):
    model = TaskMember
    extra = 0
    autocomplete_fields = ("user",)

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("__str__", "project", "status", "priority", "assignee", "due_date", "delivered_date", "created_at")
    list_filter = ("status", "priority", "project")
    search_fields = ("title", "key", "description")
    autocomplete_fields = ("project", "assignee", "labels")
    inlines = [TaskMemberInline]

@admin.register(TaskMember)
class TaskMemberAdmin(admin.ModelAdmin):
    list_display = ("task", "user", "role")
    list_filter = ("role",)
    search_fields = ("task__title", "task__key", "user__username", "user__email")
    autocomplete_fields = ("task", "user")
