# commits/services/sync.py
from __future__ import annotations

import re
from typing import Callable, Optional, Dict, Any

from django.db import transaction

from projects.models import Project
from tasck.models import Task
from commits.models import Commit, MainBranchSnapshot
from projects.services import gitea as gitea_api  # reaproveita o service já existente


TASK_KEY_PATTERN = re.compile(r"\b([A-Z0-9_-]+)-(\d+)\b")  # ex: PROJ-123


def _project_repo_info(project: Project) -> tuple[str, str, str]:
    """
    Retorna (owner, repo, branch_default) para o projeto.
    """
    owner = project.repo_owner
    repo = project.repo_name or project.name
    branch = project.default_branch or "main"
    return owner, repo, branch


def sync_commits_for_project(project: Project, *, branch: Optional[str] = None, limit: int = 100) -> list[Commit]:
    """
    Busca commits no Gitea para o repo do projeto e salva/atualiza em Commit.
    Por enquanto, pega só a primeira página (limit).
    """
    owner, repo, default_branch = _project_repo_info(project)
    branch = branch or default_branch

    raw_commits = gitea_api.list_commits(owner, repo, branch=branch, page=1, limit=limit)

    commits: list[Commit] = []
    for c in raw_commits:
        sha = c.get("sha") or c.get("id")
        if not sha:
            continue

        commit_data = c.get("commit", {}) or {}
        author = commit_data.get("author") or {}
        stats = c.get("stats") or {}
        files_changed = len(c.get("files") or [])

        obj, _created = Commit.objects.update_or_create(
            repo_owner=owner,
            repo_name=repo,
            sha=sha,
            defaults={
                "project": project,
                "branch": branch,
                "kind": Commit.Kind.MAIN,  # se estiver pegando da main
                "title": commit_data.get("message", "").splitlines()[0][:300],
                "message": commit_data.get("message", "") or "",
                "html_url": c.get("html_url", ""),
                "author_name": author.get("name", "") or "",
                "author_email": author.get("email", "") or "",
                "committed_date": author.get("date"),
                "additions": int(stats.get("additions") or 0),
                "deletions": int(stats.get("deletions") or 0),
                "files_changed": int(files_changed),
            },
        )
        commits.append(obj)

    return commits


def link_commits_to_tasks(project: Project) -> None:
    """
    Tenta vincular commits a tasks com base na presença da key no título/mensagem.
    Ex: "TASK-123 Corrige bug" → Task.project.key == "TASK" e Task.key contém "123" etc.

    Aqui você pode ajustar o padrão conforme a convenção de chave que usar.
    """
    # Carrega tasks do projeto uma vez só
    tasks_by_key: dict[str, Task] = {}
    for t in Task.objects.filter(project=project).only("id", "project_id", "key", "project__key"):
        full_key = f"{t.project.key}-{t.key}".upper()
        tasks_by_key[full_key] = t

    commits = Commit.objects.filter(project=project, task__isnull=True)

    for commit in commits:
        text = f"{commit.title}\n{commit.message}"
        match = TASK_KEY_PATTERN.search(text.upper())
        if not match:
            continue

        # Ex: PROJ-123
        full_key = match.group(0)
        task = tasks_by_key.get(full_key)
        if not task:
            continue

        commit.task = task
        commit.save(update_fields=["task"])


def update_main_snapshot_for_project(
    project: Project,
    *,
    ai_summarize_func: Callable[[Project, Commit], Dict[str, Any]],
) -> Optional[MainBranchSnapshot]:
    """
    - Busca o commit HEAD da main.
    - Cria/atualiza o Commit correspondente.
    - Chama a IA para gerar summary/chunks/vector_store_id.
    - Marca o novo snapshot como ativo e desativa os anteriores.
    """
    owner, repo, default_branch = _project_repo_info(project)

    # Pega só o commit mais recente (HEAD)
    raw_commits = gitea_api.list_commits(owner, repo, branch=default_branch, page=1, limit=1)
    if not raw_commits:
        return None

    c = raw_commits[0]
    sha = c.get("sha") or c.get("id")
    commit_data = c.get("commit", {}) or {}
    author = commit_data.get("author") or {}
    stats = c.get("stats") or {}
    files_changed = len(c.get("files") or [])

    commit_obj, _created = Commit.objects.update_or_create(
        repo_owner=owner,
        repo_name=repo,
        sha=sha,
        defaults={
            "project": project,
            "branch": default_branch,
            "kind": Commit.Kind.MAIN,
            "title": commit_data.get("message", "").splitlines()[0][:300],
            "message": commit_data.get("message", "") or "",
            "html_url": c.get("html_url", ""),
            "author_name": author.get("name", "") or "",
            "author_email": author.get("email", "") or "",
            "committed_date": author.get("date"),
            "additions": int(stats.get("additions") or 0),
            "deletions": int(stats.get("deletions") or 0),
            "files_changed": int(files_changed),
        },
    )

    # Chama a IA (função injetada)
    ai_result = ai_summarize_func(project, commit_obj) or {}
    summary = ai_result.get("summary", "")
    chunks = ai_result.get("chunks")
    vector_store_id = ai_result.get("vector_store_id", "")

    if not summary:
        # se não conseguiu gerar resumo, não cria snapshot
        return None

    with transaction.atomic():
        # desativa snapshots antigos
        MainBranchSnapshot.objects.filter(project=project, is_active=True).update(is_active=False)

        snapshot, _ = MainBranchSnapshot.objects.update_or_create(
            project=project,
            commit=commit_obj,
            defaults={
                "summary": summary,
                "chunks": chunks,
                "vector_store_id": vector_store_id,
                "is_active": True,
            },
        )

    return snapshot
