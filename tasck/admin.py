from __future__ import annotations

from django.contrib import admin

from .models import Task, Label, TaskMember, TaskMessage


class TaskMemberInline(admin.TabularInline):
    model = TaskMember
    extra = 0


class TaskMessageInline(admin.TabularInline):
    model = TaskMessage
    extra = 0
    readonly_fields = ("agent", "author_name", "created_at")
    fields = ("agent", "author_name", "text", "created_at")
    can_delete = False


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "key", "title", "status", "priority", "assignee", "created_at")
    list_filter = ("status", "priority", "project")
    search_fields = ("title", "description", "key", "project__name", "project__key")
    autocomplete_fields = ("project", "assignee", "reporter")
    inlines = [TaskMemberInline, TaskMessageInline]


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "color")
    search_fields = ("name",)


@admin.register(TaskMember)
class TaskMemberAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "user", "role")
    list_filter = ("role",)
    search_fields = ("task__title", "task__key", "user__username")


@admin.register(TaskMessage)
class TaskMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "task", "agent", "author_name", "created_at")
    list_filter = ("agent", "created_at")
    search_fields = ("task__title", "task__key", "author_name", "text")
    readonly_fields = ("created_at",)
