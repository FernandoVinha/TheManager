# commits/services/ai.py
from __future__ import annotations
from typing import Dict, Any

from projects.models import Project
from commits.models import Commit


def summarize_main_with_ai(project: Project, commit: Commit) -> Dict[str, Any]:
    """
    STUB: aqui você depois pluga OpenAI, etc.
    Por enquanto, devolve um resumo fake baseado nos dados do commit.
    """
    summary = (
        f"Project {project.name} at {commit.sha[:7]}.\n\n"
        f"Last commit: {commit.title}\n"
        f"Author: {commit.author_name} <{commit.author_email}>\n"
        f"Additions: {commit.additions}, deletions: {commit.deletions}, files changed: {commit.files_changed}."
    )

    return {
        "summary": summary,
        "chunks": None,
        "vector_store_id": "",
    }
