#commits/models.py
from __future__ import annotations

from django.db import models

from projects.models import Project
from tasck.models import Task


# ============================================================
# Commit (novo modelo unificado para IA, métricas, forks e main)
# ============================================================

class Commit(models.Model):
    """
    Representa um commit rastreado pelo sistema (main ou forks).

    Este modelo será usado para IA, métricas de código, RAG,
    avaliação de qualidade e vínculo com tasks.
    """

    class Kind(models.TextChoices):
        MAIN = "main", "Main branch"
        FORK = "fork", "User fork"
        OTHER = "other", "Other"

    # Projeto ao qual o commit pertence
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="commits",
    )

    # Commit pode opcionalmente estar ligado a uma task
    task = models.ForeignKey(
        Task,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_commits",   # <--- EVITA conflito com TaskCommit
        help_text="Commits rastreados pelo app 'commits' (IA, métricas, etc).",
    )

    # Origem no Gitea
    repo_owner = models.CharField(max_length=120)
    repo_name = models.CharField(max_length=120)
    branch = models.CharField(max_length=120, blank=True)

    kind = models.CharField(
        max_length=16,
        choices=Kind.choices,
        default=Kind.OTHER,
        db_index=True,
    )

    # Identificação do commit
    sha = models.CharField(max_length=64, db_index=True)
    title = models.CharField(max_length=300)
    message = models.TextField(blank=True)
    html_url = models.URLField(blank=True)

    # Dados do autor
    author_name = models.CharField(max_length=160, blank=True)
    author_email = models.CharField(max_length=160, blank=True)
    committed_date = models.DateTimeField(null=True, blank=True)

    # Métricas de alteração
    additions = models.IntegerField(default=0)
    deletions = models.IntegerField(default=0)
    files_changed = models.IntegerField(default=0)

    # -------------------------
    # IA – avaliação da qualidade do commit
    # -------------------------

    processed = models.BooleanField(
        default=False,
        help_text="Se este commit já foi processado pela IA.",
    )

    ai_score = models.IntegerField(
        null=True,
        blank=True,
        help_text="Nota da IA (0–10) para qualidade do código.",
    )

    code_quality_text = models.TextField(
        blank=True,
        help_text="Comentário da IA sobre a qualidade do código.",
    )

    resolution_text = models.TextField(
        blank=True,
        help_text="Descrição de como este commit ajuda a resolver a task.",
    )

    ai_payload = models.JSONField(
        null=True,
        blank=True,
        help_text="Metadados / resposta bruta da IA.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["repo_owner", "repo_name", "sha"],
                name="uniq_commit_repo_sha",
            )
        ]
        ordering = ["-committed_date", "-id"]

    def __str__(self) -> str:
        return f"{self.repo_owner}/{self.repo_name}@{self.sha[:7]}"


# ============================================================
# MainBranchSnapshot — RAG do estado do projeto no HEAD da main
# ============================================================

class MainBranchSnapshot(models.Model):
    """
    Armazena um snapshot RAG do momento atual do HEAD da main.
    Sempre que o main muda, um novo snapshot pode ser criado.
    """

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="main_snapshots",
    )

    commit = models.OneToOneField(
        Commit,
        on_delete=models.CASCADE,
        related_name="main_snapshot",
        help_text="Commit HEAD da main quando este snapshot foi gerado.",
    )

    summary = models.TextField(
        help_text="Resumo em linguagem natural do estado atual do projeto.",
    )

    chunks = models.JSONField(
        null=True,
        blank=True,
        help_text="Chunks usados no RAG (se houver).",
    )

    vector_store_id = models.CharField(
        max_length=200,
        blank=True,
        help_text="ID da collection no vector-store externo, se usar.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(
        default=True,
        help_text="Snapshot atual ativo do projeto.",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "commit"],
                name="uniq_main_snapshot_project_commit",
            )
        ]

    def __str__(self) -> str:
        return f"{self.project.key} @ {self.commit.sha[:7]}"
