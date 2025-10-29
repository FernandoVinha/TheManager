# projects/signals.py
from __future__ import annotations

import os
import stat
import subprocess
import shutil
from pathlib import Path

from django.conf import settings
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils.timezone import now

from .models import Project


# =========================
# Helpers
# =========================

def _run(cmd: list[str], cwd: Path):
    subprocess.run(cmd, cwd=str(cwd), check=True)

def _write(path: Path, content: str = ""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def _repo_root() -> Path:
    return Path(getattr(settings, "PROJECTS_REPO_ROOT", Path(settings.BASE_DIR) / "repos")).resolve()

def _project_dir(instance: Project) -> Path:
    folder_name = f"{instance.slug}-{instance.pk}"
    return (_repo_root() / folder_name).resolve()

def _safe_under_repo_root(path: Path) -> bool:
    try:
        return _repo_root() in path.parents or path == _repo_root()
    except Exception:
        return False

def _on_rm_error(func, path, exc_info):
    # Tenta liberar permissões e repetir a operação (útil para .git/objects)
    try:
        os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass
    try:
        func(path)
    except Exception:
        pass


# =========================
# post_save → cria repo
# =========================

@receiver(post_save, sender=Project)
def create_git_repo_scaffold(sender, instance: Project, created: bool, **kwargs):
    if not created:
        return
    project_dir = _project_dir(instance)
    project_dir.mkdir(parents=True, exist_ok=True)

    readme = (
        f"# {instance.name}\n\n"
        f"**Gerente:** {getattr(instance.manager, 'email', instance.manager_id)}\n\n"
        f"**Metodologia:** {instance.get_methodology_display()}\n\n"
        f"**Criado em:** {now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"{(instance.description or '').strip()}\n"
    )
    gitignore = """
# Python
__pycache__/
*.py[cod]
*$py.class

# Virtual env
.venv/
venv/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Django
staticfiles/
media/
""".strip() + "\n"

    try:
        _write(project_dir / "README.md", readme)
        _write(project_dir / "Dockerfile", "")
        _write(project_dir / "docker-compose.yml", "")
        _write(project_dir / ".gitignore", gitignore)

        _run(["git", "init", "-b", "main"], project_dir)
        _run(["git", "add", "."], project_dir)
        _run(["git", "commit", "-m", "Initial scaffold"], project_dir)
        print(f"[projects] created repo at: {project_dir}")
    except Exception as e:
        print(f"[projects] scaffold error: {e}")


# =========================
# pre_delete → remove repo
# =========================

@receiver(pre_delete, sender=Project)
def remove_git_repo_folder(sender, instance: Project, **kwargs):
    try:
        project_dir = _project_dir(instance)
        if not _safe_under_repo_root(project_dir):
            print(f"[projects] skip delete (unsafe path): {project_dir}")
            return
        if project_dir.exists():
            shutil.rmtree(project_dir, onerror=_on_rm_error)
            print(f"[projects] deleted repo folder: {project_dir}")
        else:
            print(f"[projects] repo folder does not exist: {project_dir}")
    except Exception as e:
        print(f"[projects] repo delete error: {e}")
