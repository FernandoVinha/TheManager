#commits/management/commands/update_main_snapshots.py
from __future__ import annotations

from django.core.management.base import BaseCommand

from projects.models import Project
from commits.services.sync import update_main_snapshot_for_project
from commits.services.ai import summarize_main_with_ai


class Command(BaseCommand):
    help = "Atualiza snapshots da branch main para todos os projetos."

    def handle(self, *args, **options):
        projects = Project.objects.all().order_by("id")
        total = projects.count()
        self.stdout.write(f"Processando {total} projetos...")

        for i, project in enumerate(projects, start=1):
            self.stdout.write(f"[{i}/{total}] Projeto {project.id} - {project.name}...", ending="")
            snapshot = update_main_snapshot_for_project(
                project,
                ai_summarize_func=summarize_main_with_ai,
            )
            if snapshot is None:
                self.stdout.write(" nenhum snapshot gerado.")
            else:
                self.stdout.write(
                    f" snapshot criado/atualizado para commit {snapshot.commit.sha[:7]}."
                )

        self.stdout.write("Concluído.")
