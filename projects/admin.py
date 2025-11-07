from django.contrib import admin
from .models import Project, ProjectMember

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "methodology", "repo_owner", "repo_name", "visibility", "created_at")
    search_fields = ("name", "key", "repo_owner", "repo_name")
    list_filter = ("methodology", "visibility", "created_at")
    readonly_fields = ("gitea_repo_url",)

@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = ("project", "user", "role")
    search_fields = ("project__name", "user__username")
    list_filter = ("role",)
