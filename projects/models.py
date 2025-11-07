from __future__ import annotations
from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL

class Project(models.Model):
    class Methodology(models.TextChoices):
        SCRUM = "scrum", "Scrum"
        KANBAN = "kanban", "Kanban"
        XP = "xp", "Extreme Programming (XP)"

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        PUBLIC = "public", "Public"

    name = models.CharField(max_length=120, unique=True)
    key = models.SlugField(max_length=64, unique=True, help_text="Short slug used in URLs and integrations")
    methodology = models.CharField(max_length=12, choices=Methodology.choices, default=Methodology.SCRUM)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="owned_projects")

    # Gitea repo settings
    repo_owner = models.CharField(max_length=120, help_text="User or organization that will own the repo in Gitea")
    repo_name = models.CharField(max_length=120, blank=True, help_text="Repository name in Gitea (defaults to project name)")
    visibility = models.CharField(max_length=12, choices=Visibility.choices, default=Visibility.PRIVATE)
    default_branch = models.CharField(max_length=64, default="main")
    auto_init = models.BooleanField(default=True, help_text="Create initial README in the repo")
    gitea_repo_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Practical toggles for different methodologies
    sprint_length_days = models.PositiveIntegerField(default=14, help_text="Sprint length (Scrum)")
    wip_limit = models.PositiveIntegerField(default=3, help_text="Default WIP per column (Kanban)")
    xp_pair_programming = models.BooleanField(default=True, help_text="Prefer pair programming (XP)")

    def __str__(self):
        return self.name


class ProjectMember(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MAINTAINER = "maintainer", "Maintainer"
        DEVELOPER = "developer", "Developer"
        REPORTER = "reporter", "Reporter"
        GUEST = "guest", "Guest"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="project_memberships")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.DEVELOPER)

    class Meta:
        unique_together = (("project", "user"),)

    def __str__(self):
        return f"{self.user} @ {self.project} ({self.role})"
