# tasck/models.py
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from projects.models import Project

User = settings.AUTH_USER_MODEL


class Label(models.Model):
    """
    Rótulo simples, reutilizável entre tasks (ex.: "backend", "bug", "ux").
    """
    name = models.CharField(max_length=40)
    color = models.CharField(
        max_length=9,
        default="#6b4ce6",
        help_text="CSS hex (#RRGGBB ou #RRGGBBAA)",
    )

    class Meta:
        unique_together = (("name", "color"),)
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "todo", "To do"
        IN_PROGRESS = "in_progress", "In progress"
        REVIEW = "review", "In review"
        VERIFIED = "verified", "Verified"   # → tentará PR+merge automático
        DONE = "done", "Done"
        FAILED = "failed", "Failed"         # → erro no merge/integração ou outros

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="tasks"
    )

    title = models.CharField(max_length=160)
    key = models.SlugField(
        max_length=64,
        help_text="Short key (unique per project)",
    )
    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.TODO, db_index=True
    )
    priority = models.CharField(
        max_length=16, choices=Priority.choices, default=Priority.MEDIUM, db_index=True
    )

    reporter = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="reported_tasks",
        help_text="Quem criou/relatou a task"
    )
    assignee = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_tasks", help_text="Responsável atual"
    )

    labels = models.ManyToManyField(Label, blank=True, related_name="tasks")

    # Datas
    due_date = models.DateField(
        null=True, blank=True, help_text="Data prevista de entrega"
    )
    delivered_date = models.DateField(
        null=True, blank=True, help_text="Data de entrega (real)"
    )

    # Metadados do fork no Gitea (criados quando a task é criada)
    gitea_fork_owner = models.CharField(max_length=120, blank=True)
    gitea_fork_name = models.CharField(max_length=120, blank=True)
    gitea_fork_url = models.URLField(blank=True)

    # Anexo simples (opcional)
    attachment = models.FileField(
        upload_to="task_attachments/", null=True, blank=True
    )

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("project", "key"),)
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["project", "priority"]),
        ]

    def __str__(self) -> str:
        return f"{self.project.key}-{self.key}: {self.title}"

    def save(self, *args, **kwargs):
        # Se não vier uma key, gera um slug do título (limitado ao tamanho do campo)
        if not self.key:
            base = slugify(self.title)[: self._meta.get_field("key").max_length]
            self.key = base or "task"
        super().save(*args, **kwargs)


class TaskMember(models.Model):
    """
    Membros por task, com papel semelhante ao de ProjectMember.
    Útil quando uma task tem colaboradores específicos com papéis distintos.
    """
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MAINTAINER = "maintainer", "Maintainer"
        DEVELOPER = "developer", "Developer"
        REPORTER = "reporter", "Reporter"
        GUEST = "guest", "Guest"

    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="task_memberships"
    )
    role = models.CharField(
        max_length=16, choices=Role.choices, default=Role.DEVELOPER
    )

    class Meta:
        unique_together = (("task", "user"),)

    def __str__(self) -> str:
        return f"{self.user} @ {self.task} ({self.role})"


class TaskMessage(models.Model):
    """
    Mensageria básica por Task:
    - `author_name` é texto livre (pode ser humano, bot, agente externo, etc.)
    - `agent` classifica a origem (user/gitea/system)
    - `payload` guarda metadados (ex.: respostas da API do Gitea)
    """
    class Agent(models.TextChoices):
        USER = "user", "User"
        GITEA = "gitea", "Gitea"
        SYSTEM = "system", "System"

    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name="messages"
    )
    agent = models.CharField(
        max_length=16, choices=Agent.choices, default=Agent.USER
    )
    author_name = models.CharField(
        max_length=120, blank=True,
        help_text="Nome livre do autor (pessoa, bot ou agente externo)"
    )
    text = models.TextField()
    payload = models.JSONField(
        null=True, blank=True,
        help_text="Metadata opcional, ex.: resposta crua da API"
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
