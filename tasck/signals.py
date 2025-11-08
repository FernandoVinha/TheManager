# tasck/signals.py
from __future__ import annotations
import logging
from django.db.models.signals import pre_save, post_save
from django.db import transaction
from django.dispatch import receiver
from .models import Task, TaskMessage
from projects.services import gitea as gitea_api

log = logging.getLogger(__name__)

@receiver(pre_save, sender=Task)
def _capture_old_status(sender, instance: Task, **kwargs):
    if instance.pk:
        try:
            old = sender.objects.only("status").get(pk=instance.pk)
            instance._old_status = old.status  # efêmero
        except sender.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

def _post_gitea_message(task_id: int, text: str, payload: dict | None = None):
    TaskMessage.objects.create(
        task_id=task_id,
        agent=TaskMessage.Agent.GITEA,
        text=text,
        payload=payload or None,
    )

@receiver(post_save, sender=Task)
def _on_verified_try_merge(sender, instance: Task, created: bool, **kwargs):
    # só reage em updates para VERIFIED
    if created:
        return
    old_status = getattr(instance, "_old_status", None)
    if instance.status != Task.Status.VERIFIED or old_status == Task.Status.VERIFIED:
        return

    project = instance.project
    if not instance.gitea_fork_owner or not instance.gitea_fork_name:
        # sem fork conhecido — registra info e encerra
        transaction.on_commit(lambda: _post_gitea_message(instance.pk, "No fork metadata found on task; skipping PR/merge."))
        return

    src_owner = instance.gitea_fork_owner
    src_repo  = instance.gitea_fork_name

    dst_owner = project.repo_owner
    dst_repo  = project.repo_name or project.name

    def _do_pr_and_merge(task_pk: int):
        try:
            # descobre branchs default
            src_info = gitea_api.get_repo(src_owner, src_repo)
            dst_info = gitea_api.get_repo(dst_owner, dst_repo)
            head_branch = (src_info.get("default_branch") or project.default_branch or "main")
            base_branch = (dst_info.get("default_branch") or project.default_branch or "main")

            head = f"{src_owner}:{head_branch}"
            title = f"Task {instance.project.key}-{instance.key} — merge to {base_branch}"

            pr = gitea_api.create_pull_request(dst_owner, dst_repo, head=head, base_branch=base_branch, title=title)
            pr_index = pr.get("number") or pr.get("index")

            _post_gitea_message(task_pk, f"PR created: #{pr_index}", payload={"pr": pr})

            merge = gitea_api.merge_pull_request(dst_owner, dst_repo, pr_index,
                                                 method="merge",
                                                 title=f"Merge {title}",
                                                 message=f"Auto-merge from task {instance.key}",
                                                 delete_branch=False)

            _post_gitea_message(task_pk, f"PR #{pr_index} merged successfully.", payload={"merge": merge})

            # opcional: marcar como DONE no sucesso
            sender.objects.filter(pk=task_pk).update(status=Task.Status.DONE)

        except Exception as e:
            # registra erro e marca FAILED
            try:
                # tentar extrair corpo do HTTPError se for o caso
                if hasattr(e, "read"):
                    body = e.read().decode("utf-8", errors="replace")
                    payload = {"error": str(e), "body": body}
                else:
                    payload = {"error": str(e)}
            except Exception:
                payload = {"error": str(e)}

            _post_gitea_message(task_pk, "Merge failed.", payload=payload)
            sender.objects.filter(pk=task_pk).update(status=Task.Status.FAILED)

    transaction.on_commit(lambda: _do_pr_and_merge(instance.pk))
