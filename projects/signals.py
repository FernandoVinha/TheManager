# projects/signals.py
from __future__ import annotations

import logging
from typing import Callable

from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Project, ProjectMember
from .services import gitea as gitea

log = logging.getLogger(__name__)


def _permission_from_role(role: str) -> str:
    """
    Mapeia a role do projeto para a permissão no Gitea.
    """
    mapping = {
        ProjectMember.Role.OWNER: "admin",
        ProjectMember.Role.MAINTAINER: "admin",
        ProjectMember.Role.DEVELOPER: "write",
        ProjectMember.Role.REPORTER: "read",
        ProjectMember.Role.GUEST: "read",
    }
    return mapping.get(role, "read")


def _on_commit(fn: Callable[[], None]) -> None:
    """
    Helper: garante que a chamada à API do Gitea só ocorra após o commit da transação.
    """
    transaction.on_commit(fn)


@receiver(post_save, sender=Project)
def create_repo_for_project(sender, instance: Project, created: bool, **kwargs):
    """
    Ao criar um Project, cria o repositório correspondente no Gitea
    sob o owner (usuário/organização) definido em `repo_owner`,
    usando o token admin + header Sudo.

    Observações:
    - Executa apenas após o commit do banco (via transaction.on_commit)
    - Atualiza `repo_name` (caso o Gitea normalize) e `gitea_repo_url`
    - Garante o ProjectMember OWNER para o `instance.owner`
    """
    if not created:
        return

    def _do():
        repo_name = instance.repo_name or instance.name
        try:
            # Valida se o owner (usuário OU organização) existe no Gitea.
            gitea.ensure_owner_exists(instance.repo_owner)

            # Cria o repo via /user/repos com Sudo=<repo_owner>.
            resp = gitea.create_repo(
                owner=instance.repo_owner,
                name=repo_name,
                description=instance.description or instance.name,
                private=(instance.visibility == Project.Visibility.PRIVATE),
                default_branch=instance.default_branch or "main",
                auto_init=instance.auto_init,
            )

            effective_name = resp.get("name", repo_name)
            url = gitea.repo_web_url(instance.repo_owner, effective_name)

            # Atualiza o registro com o nome final e URL.
            sender.objects.filter(pk=instance.pk).update(
                repo_name=effective_name,
                gitea_repo_url=url,
            )

            # Garante o membro OWNER para o criador do projeto.
            ProjectMember.objects.get_or_create(
                project=instance,
                user=instance.owner,
                defaults={"role": ProjectMember.Role.OWNER},
            )

            log.info(
                "Gitea repo created for project '%s' at %s",
                instance.name,
                url,
            )

        except Exception as e:
            # Importante: como estamos em on_commit, o Project já foi persistido.
            # Logamos o erro para tratamento posterior (ex.: job de reconciliação).
            log.exception(
                "Failed to create Gitea repository for project '%s' (owner=%s, name=%s): %s",
                instance.name,
                instance.repo_owner,
                repo_name,
                e,
            )

    _on_commit(_do)


@receiver(post_save, sender=ProjectMember)
def add_or_sync_member_in_repo(sender, instance: ProjectMember, created: bool, **kwargs):
    """
    Ao criar (ou alterar) um ProjectMember:
    - Se criado: adiciona colaborador no repo com a permissão mapeada.
    - Se atualizado: re-sincroniza a permissão (útil quando a role muda).

    Observações:
    - Executa após commit para evitar inconsistências.
    - Se o repositório ainda não existir (e.g. criação concorrente), apenas loga aviso.
    """
    def _do():
        project = instance.project
        # Se o repo ainda não foi criado/atualizado (“URL” ausente), evitamos falhar aqui.
        if not (project.repo_owner and (project.repo_name or project.name) and project.gitea_repo_url):
            log.warning(
                "Skipping Gitea collaborator sync: repo not ready for project '%s' (id=%s).",
                project.name,
                project.pk,
            )
            return

        try:
            # Garante que o owner existe (user/org). Não valida o usuário aqui,
            # pois o add_collaborator já falhará de forma clara se não existir.
            gitea.ensure_owner_exists(project.repo_owner)

            perm = _permission_from_role(instance.role)
            gitea.add_collaborator(
                project.repo_owner,
                project.repo_name or project.name,
                instance.user.username,
                perm,
            )

            action = "added" if created else "synced"
            log.info(
                "Gitea collaborator %s (%s) %s on %s/%s with perm=%s",
                instance.user.username,
                instance.role,
                action,
                project.repo_owner,
                project.repo_name or project.name,
                perm,
            )

        except Exception as e:
            log.exception(
                "Failed to %s collaborator in repo (%s/%s): user=%s, role=%s, err=%s",
                "add" if created else "sync",
                project.repo_owner,
                project.repo_name or project.name,
                instance.user.username,
                instance.role,
                e,
            )

    _on_commit(_do)


@receiver(post_delete, sender=ProjectMember)
def remove_member_from_repo(sender, instance: ProjectMember, **kwargs):
    """
    Ao remover um ProjectMember, remove também o colaborador do repo.
    Executa após commit.
    """
    def _do():
        project = instance.project
        # Caso o repo ainda não exista ou não tenha sido configurado, apenas registra aviso.
        if not (project.repo_owner and (project.repo_name or project.name)):
            log.warning(
                "Skipping Gitea collaborator removal: repo not ready for project '%s' (id=%s).",
                project.name,
                project.pk,
            )
            return

        try:
            gitea.remove_collaborator(
                project.repo_owner,
                project.repo_name or project.name,
                instance.user.username,
            )
            log.info(
                "Gitea collaborator removed: user=%s from %s/%s",
                instance.user.username,
                project.repo_owner,
                project.repo_name or project.name,
            )
        except Exception as e:
            # Remoção pode falhar se o usuário já não for colaborador; tratamos como aviso.
            log.warning(
                "Failed to remove collaborator from repo (%s/%s): user=%s, err=%s (ignored)",
                project.repo_owner,
                project.repo_name or project.name,
                instance.user.username,
                e,
            )

    _on_commit(_do)


@receiver(post_save, sender=Project)
def ensure_owner_membership(sender, instance: Project, created: bool, **kwargs):
    if not created:
        return
    def _do():
        ProjectMember.objects.get_or_create(
            project=instance,
            user=instance.owner,
            defaults={"role": ProjectMember.Role.OWNER},
        )
    transaction.on_commit(_do)