from __future__ import annotations
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Project, ProjectMember
from .services import gitea as gitea

log = logging.getLogger(__name__)

def _permission_from_role(role: str) -> str:
    # Map project role → Gitea permission (read|write|admin)
    mapping = {
        ProjectMember.Role.OWNER: "admin",
        ProjectMember.Role.MAINTAINER: "admin",
        ProjectMember.Role.DEVELOPER: "write",
        ProjectMember.Role.REPORTER: "read",
        ProjectMember.Role.GUEST: "read",
    }
    return mapping.get(role, "read")

@receiver(post_save, sender=Project)
def create_repo_for_project(sender, instance: Project, created: bool, **kwargs):
    if not created:
        return
    repo_name = instance.repo_name or instance.name
    try:
        # Validate that the repo owner exists in Gitea (user or org)
        gitea.ensure_user_exists(instance.repo_owner)
        resp = gitea.create_repo(
            owner=instance.repo_owner,
            name=repo_name,
            description=instance.description or instance.name,
            private=(instance.visibility == Project.Visibility.PRIVATE),
            default_branch=instance.default_branch or "main",
            auto_init=instance.auto_init,
        )
        url = gitea.repo_web_url(instance.repo_owner, resp.get("name", repo_name))
        sender.objects.filter(pk=instance.pk).update(
            repo_name=resp.get("name", repo_name),
            gitea_repo_url=url,
        )
        # Ensure the project owner is a member with OWNER role
        ProjectMember.objects.get_or_create(project=instance, user=instance.owner,
                                            defaults={"role": ProjectMember.Role.OWNER})
    except Exception as e:
        log.exception("Failed to create Gitea repository for project %s: %s", instance.name, e)
        raise

@receiver(post_save, sender=ProjectMember)
def add_member_to_repo(sender, instance: ProjectMember, created: bool, **kwargs):
    if not created:
        # Optional: if role changed, you may want to re-apply permission
        pass
    project = instance.project
    try:
        gitea.ensure_user_exists(instance.user.username)
        perm = _permission_from_role(instance.role)
        gitea.add_collaborator(project.repo_owner, project.repo_name or project.name,
                               instance.user.username, perm)
    except Exception as e:
        log.exception("Failed to add collaborator to repo (%s/%s): %s",
                      project.repo_owner, project.repo_name or project.name, e)
        raise

@receiver(post_delete, sender=ProjectMember)
def remove_member_from_repo(sender, instance: ProjectMember, **kwargs):
    project = instance.project
    try:
        gitea.remove_collaborator(project.repo_owner, project.repo_name or project.name, instance.user.username)
    except Exception as e:
        log.warning("Failed to remove collaborator from repo (%s/%s): %s (ignored)",
                    project.repo_owner, project.repo_name or project.name, e)
