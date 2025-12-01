from __future__ import annotations

from typing import Optional

from django.db import transaction

from projects.models import Project
from ..models import Commit, MainBranchSnapshot  # <- repara nos dois pontos!


def update_main_snapshot_for_project(
    project: Project,
    *,
    ai_summarize_func,
) -> Optional[MainBranchSnapshot]:
    """
    Versão simples: NÃO chama Gitea ainda.

    - Pega o commit mais recente marcado como MAIN no banco
    - Se não houver, não faz nada (retorna None)
    - Se já existir snapshot ativo para esse commit, só retorna o existente
    - Se não, chama a função de IA e cria um novo MainBranchSnapshot

    Depois, quando você tiver o sync com Gitea populando Commits (Kind.MAIN),
    esse comando já vai funcionar em cima disso.
    """

    # 1) pegar o commit MAIN mais recente desse projeto
    commit = (
        Commit.objects
        .filter(project=project, kind=Commit.Kind.MAIN)
        .order_by("-committed_date", "-id")
        .first()
    )

    if not commit:
        # ainda não temos commits MAIN no banco para este projeto
        return None

    # 2) se já existe snapshot ativo para esse commit, retorna ele
    existing = (
        MainBranchSnapshot.objects
        .filter(project=project, commit=commit, is_active=True)
        .first()
    )
    if existing:
        return existing

    # 3) chama a IA para gerar summary/chunks
    ai_result = ai_summarize_func(project=project, commit=commit)
    summary = ai_result.get("summary", "")
    chunks = ai_result.get("chunks")
    vector_store_id = ai_result.get("vector_store_id", "")

    if not summary:
        # IA não retornou nada — não criamos snapshot
        return None

    # 4) cria snapshot novo e desativa os anteriores
    with transaction.atomic():
        MainBranchSnapshot.objects.filter(
            project=project,
            is_active=True,
        ).exclude(commit=commit).update(is_active=False)

        snapshot = MainBranchSnapshot.objects.create(
            project=project,
            commit=commit,
            summary=summary,
            chunks=chunks,
            vector_store_id=vector_store_id,
            is_active=True,
        )

    return snapshot
