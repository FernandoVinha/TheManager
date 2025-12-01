from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from projects.models import Project

User = settings.AUTH_USER_MODEL


class Label(models.Model):
    name = models.CharField(max_length=40)
    color = models.CharField(
        max_length=9,
        default="#6b4ce6",
        help_text="CSS hex (#RRGGBB ou #RRGGBBAA)",
    )

    class Meta:
        constraints = [
            # Nome único; cor pode ser alterada
            models.UniqueConstraint(fields=["name"], name="uniq_label_name"),
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "todo", "To do"
        IN_PROGRESS = "in_progress", "In progress"
        REVIEW = "review", "In review"
        VERIFIED = "verified", "Verified"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")

    title = models.CharField(max_length=160)
    key = models.SlugField(max_length=64, help_text="Short key (unique per project)")
    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TODO,
        db_index=True,
    )
    priority = models.CharField(
        max_length=16,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        db_index=True,
    )

    reporter = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="reported_tasks",
        help_text="Quem criou/relatou a task",
    )
    assignee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
        help_text="Responsável atual",
    )

    labels = models.ManyToManyField(Label, blank=True, related_name="tasks")

    due_date = models.DateField(null=True, blank=True)
    delivered_date = models.DateField(null=True, blank=True)

    gitea_fork_owner = models.CharField(max_length=120, blank=True)
    gitea_fork_name = models.CharField(max_length=120, blank=True)
    gitea_fork_url = models.URLField(blank=True)

    attachment = models.FileField(upload_to="task_attachments/", null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "key"], name="uniq_task_project_key"),
        ]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["project", "priority"]),
        ]

    def __str__(self) -> str:
        return f"{self.project.key}-{self.key}: {self.title}"

    def save(self, *args, **kwargs):
        """
        Gera `key` automaticamente a partir do título, garantindo unicidade por projeto.
        Ex.: "minha-task", "minha-task-2", "minha-task-3", ...
        """
        if not self.key:
            base = slugify(self.title) or "task"
            max_len = self._meta.get_field("key").max_length
            base = base[:max_len]

            key = base
            ModelClass = self.__class__

            if self.project_id:
                qs = ModelClass.objects.filter(project=self.project)
            else:
                # fallback raro (antes de setar project)
                qs = ModelClass.objects.all()

            i = 2
            while qs.filter(key=key).exists():
                suffix = f"-{i}"
                key = (base[: max_len - len(suffix)]) + suffix
                i += 1

            self.key = key

        super().save(*args, **kwargs)


class TaskMember(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MAINTAINER = "maintainer", "Maintainer"
        DEVELOPER = "developer", "Developer"
        REPORTER = "reporter", "Reporter"
        GUEST = "guest", "Guest"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="task_memberships")
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.DEVELOPER)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["task", "user"], name="uniq_task_member"),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.task} ({self.role})"


class TaskMessage(models.Model):
    class Agent(models.TextChoices):
        USER = "user", "User"
        GITEA = "gitea", "Gitea"
        SYSTEM = "system", "System"

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="messages")
    agent = models.CharField(max_length=16, choices=Agent.choices, default=Agent.USER)
    author_name = models.CharField(
        max_length=120,
        blank=True,
        help_text="Nome livre do autor",
    )
    text = models.TextField()
    payload = models.JSONField(
        null=True,
        blank=True,
        help_text="Metadata opcional (ex.: resposta da API do Gitea)",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "pk"]
        indexes = [
            models.Index(fields=["task", "created_at"]),
        ]

    def __str__(self) -> str:
        who = self.author_name or self.get_agent_display()
        return f"[{who}] {self.text[:60]}"


class TaskCommit(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="commits")
    sha = models.CharField(max_length=64, db_index=True)

    author_name = models.CharField(max_length=160, blank=True)
    author_email = models.CharField(max_length=160, blank=True)
    committed_date = models.DateTimeField(null=True, blank=True)

    title = models.CharField(max_length=300)
    message = models.TextField(blank=True)

    additions = models.IntegerField(default=0)
    deletions = models.IntegerField(default=0)
    files_changed = models.IntegerField(default=0)

    html_url = models.URLField(blank=True)

    code_quality_text = models.TextField(blank=True)
    resolution_text = models.TextField(blank=True)
    processed = models.BooleanField(
        default=False,
        help_text="Se este commit já foi processado por IA.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["task", "sha"], name="uniq_task_commit_sha"),
        ]
        ordering = ["-committed_date", "-id"]
        indexes = [
            models.Index(fields=["task", "sha"]),
            models.Index(fields=["task", "committed_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.sha[:7]} — {self.title}"
