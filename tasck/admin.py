from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from .models import Task, Label, TaskMember, TaskMessage, TaskCommit


@admin.register(Label)
class LabelAdmin(admin.ModelAdmin):
    list_display = ("name", "color_swatch")
    search_fields = ("name",)

    def color_swatch(self, obj):
        return format_html(
            '<span style="display:inline-block;width:1.1rem;height:1.1rem;border:1px solid #ccc;vertical-align:middle;background:{}"></span> {}',
            obj.color, obj.color
        )
    color_swatch.short_description = "Color"


class TaskMemberInline(admin.TabularInline):
    model = TaskMember
    extra = 0
    autocomplete_fields = ("user",)
    show_change_link = True


class TaskMessageInline(admin.StackedInline):
    model = TaskMessage
    extra = 0
    fields = ("agent", "author_name", "text", "created_at")
    readonly_fields = ("created_at",)


class TaskCommitInline(admin.TabularInline):
    model = TaskCommit
    extra = 0
    fields = (
        "sha_short", "author_name", "committed_date",
        "additions", "deletions",
        "code_quality_text", "resolution_text",
    )
    readonly_fields = ("sha_short", "author_name", "committed_date", "additions", "deletions")

    def sha_short(self, obj):
        return (obj.sha or "")[:10]
    sha_short.short_description = "SHA"


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "id", "project", "key", "title", "status", "priority",
        "assignee", "reporter", "created_at", "updated_at",
    )
    list_filter = ("status", "priority", "project")
    search_fields = ("title", "key", "description", "project__name")
    autocomplete_fields = ("project", "assignee", "reporter", "labels")
    date_hierarchy = "created_at"
    inlines = [TaskMemberInline, TaskMessageInline, TaskCommitInline]
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Basic", {
            "fields": ("project", "title", "key", "description", "attachment")
        }),
        ("Workflow", {
            "fields": ("status", "priority", "reporter", "assignee", "labels", "due_date", "delivered_date")
        }),
        ("Fork/Repo metadata", {
            "fields": ("gitea_fork_owner", "gitea_fork_name", "gitea_fork_url"),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )


@admin.register(TaskMember)
class TaskMemberAdmin(admin.ModelAdmin):
    list_display = ("task", "user", "role")
    list_filter = ("role", "task__project")
    search_fields = ("task__title", "task__key", "user__username")
    autocomplete_fields = ("task", "user")


@admin.register(TaskMessage)
class TaskMessageAdmin(admin.ModelAdmin):
    list_display = ("task", "agent", "author_name", "short_text", "created_at")
    list_filter = ("agent", "task__project")
    search_fields = ("task__title", "author_name", "text")
    autocomplete_fields = ("task",)
    readonly_fields = ("created_at",)

    def short_text(self, obj):
        return (obj.text or "")[:80]
    short_text.short_description = "Text"


@admin.register(TaskCommit)
class TaskCommitAdmin(admin.ModelAdmin):
    list_display = (
        "task", "sha_short", "author_name", "committed_date",
        "additions", "deletions",
        "quality_short", "resolves_short",
    )
    list_filter = ("task__project",)
    search_fields = ("task__title", "sha", "author_name", "message")
    autocomplete_fields = ("task",)
    readonly_fields = (
        "sha", "author_name", "author_email", "message",
        "committed_date", "additions", "deletions"
    )

    fieldsets = (
        ("Commit", {
            "fields": ("task", "sha", "author_name", "author_email", "message", "committed_date")
        }),
        ("Stats", {
            "fields": ("additions", "deletions")
        }),
        ("Review (IA / resolução)", {
            "fields": ("code_quality_text", "resolution_text")
        }),
    )

    def sha_short(self, obj):
        return (obj.sha or "")[:10]
    sha_short.short_description = "SHA"

    def quality_short(self, obj):
        return (obj.code_quality_text or "")[:40]
    quality_short.short_description = "Quality"

    def resolves_short(self, obj):
        return (obj.resolution_text or "")[:40]
    resolves_short.short_description = "Resolves"
