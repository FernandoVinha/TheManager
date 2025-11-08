from __future__ import annotations
from django.conf import settings
from django.db import models
from django.utils import timezone
from projects.models import Project

User = settings.AUTH_USER_MODEL

class Label(models.Model):
    name = models.CharField(max_length=40)
    color = models.CharField(max_length=9, default="#6b4ce6", help_text="CSS hex (#RRGGBB ou #RRGGBBAA)")

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
        DONE = "done", "Done"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=160)
    key = models.SlugField(max_length=64, help_text="Short key (unique per project)")
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TODO, db_index=True)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.MEDIUM, db_index=True)

    reporter = models.ForeignKey(User, on_delete=models.PROTECT, related_name="reported_tasks")
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tasks")

    labels = models.ManyToManyField(Label, blank=True, related_name="tasks")

    due_date = models.DateField(null=True, blank=True)
    attachment = models.FileField(upload_to="task_attachments/", null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("project", "key"),)
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.project.key}-{self.key}: {self.title}"
