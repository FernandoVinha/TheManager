from __future__ import annotations

from typing import Any, Dict

from projects.models import Project
from ..models import Commit


def summarize_main_with_ai(*, project: Project, commit: Commit) -> Dict[str, Any]:
    """
    Gera o 'snapshot' da branch main usando IA.

    Por enquanto isto é um STUB (implementação de teste):
      - Não chama nenhum modelo de IA de verdade.
      - Apenas monta um resumo textual simples com os dados do commit.

    Quando você for integrar com a IA de verdade, a ideia é:
      - Buscar o contexto que você quiser (arquivos do repo, diff, etc.).
      - Mandar isso para o modelo (OpenAI, etc.).
      - Montar um dict no formato:
          {
            "summary": "texto resumido...",
            "chunks": [...],           # opcional: lista de documentos / pedaços
            "vector_store_id": "abc",  # opcional: ID da coleção de embeddings
          }
    """

    summary_lines = [
        f"Snapshot do projeto '{project.name}' no commit {commit.sha[:7]}.",
        "",
        f"Título do commit: {commit.title}",
        f"Autor: {commit.author_name} <{commit.author_email}>",
        "",
        f"Métricas do commit:",
        f"- Additions: {commit.additions}",
        f"- Deletions: {commit.deletions}",
        f"- Files changed: {commit.files_changed}",
        "",
        "OBS: este resumo ainda é gerado sem IA real; "
        "substitua a implementação desta função para chamar o modelo que você quiser.",
    ]

    summary = "\n".join(summary_lines)

    return {
        "summary": summary,
        "chunks": None,       # depois você pode trocar por uma lista de textos/chunks
        "vector_store_id": "",  # depois você pode preencher com o ID da collection no seu vector store
    }


def review_task_commit_with_ai(*, commit: Commit) -> Dict[str, Any]:
    """
    Stub para análise de commits de fork (ligados à Task) com IA.

    Ideia de uso futuro:
      - Ler `commit.task` (título/descrição da task).
      - Ler título/mensagem do commit + métricas (additions, deletions, etc.).
      - (Opcional) buscar o diff no Gitea.
      - Mandar tudo para o modelo de IA pedindo:
          - Como esse commit ajuda a resolver a task?
          - Uma nota de 0 a 10 para a qualidade do código.
      - Retornar no formato:

          {
            "score": 8,
            "code_quality": "Texto explicando a qualidade do código...",
            "resolution": "Texto explicando como o commit ajuda na task...",
            "extra": {...}  # qualquer metadado que você quiser guardar em ai_payload
          }

    No momento, devolve apenas um conteúdo fake para teste.
    """
    task = commit.task

    task_title = task.title if task else "(sem task vinculada)"
    task_desc = (task.description or "").strip() if task else ""

    fake_score = 7  # só para testes

    code_quality = (
        f"Avaliação fake da qualidade do commit {commit.sha[:7]}.\n"
        f"Este é um placeholder – depois troque esta função para "
        f"chamar a IA de verdade."
    )

    resolution = (
        "Explicação fake de como este commit ajuda a resolver a task.\n"
        f"Título da task: {task_title}\n"
        f"Título do commit: {commit.title}"
    )

    return {
        "score": fake_score,
        "code_quality": code_quality,
        "resolution": resolution,
        "extra": {
            "task_title": task_title,
            "task_description_preview": task_desc[:200],
        },
    }
