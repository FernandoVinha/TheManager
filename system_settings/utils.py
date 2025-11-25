import os
import signal
import subprocess
from pathlib import Path

from django.conf import settings


def get_base_dir() -> Path:
    return Path(settings.BASE_DIR)


# ---------- leitura/gravação de .env ----------

def read_env_file(path: Path) -> dict:
    """
    Lê um arquivo .env simples KEY=VALUE por linha.
    Ignora comentários e linhas em branco.
    """
    data: dict[str, str] = {}
    if not path.exists():
        return data

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return data


def write_env_file(path: Path, data: dict, header: str | None = None) -> None:
    """
    Sobrescreve o arquivo .env com KEY=VALUE.
    Comentários antigos são perdidos – simples e direto.
    """
    lines: list[str] = []
    if header:
        lines.append(header.rstrip("\n"))
        lines.append("")

    for key, value in data.items():
        v = str(value).replace("\n", " ")
        lines.append(f"{key}={v}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_env_file_keys(path: Path, updates: dict, header: str | None = None) -> None:
    """
    Atualiza algumas chaves em um .env (ou cria, se não existir).
    """
    current = read_env_file(path)
    for k, v in updates.items():
        if v is not None:
            current[k] = str(v)
    write_env_file(path, current, header=header)


# ---------- recarregar django ----------

def reload_django_process() -> None:
    """
    Tenta forçar o Django a recarregar.
    Em dev com runserver, tocar um .py já dispara o autoreload.
    Em produção com Docker + restart policy, um kill pode forçar restart.
    """
    try:
        # Toca o wsgi.py para o autoreloader do runserver notar mudança
        wsgi_path = get_base_dir() / "core" / "wsgi.py"
        if wsgi_path.exists():
            wsgi_path.touch()
            return
    except Exception:
        pass

    # Fallback: tenta mandar um sinal para o próprio processo
    try:
        os.kill(os.getpid(), signal.SIGHUP)
    except Exception:
        # Último recurso: SIGINT (pode derrubar o servidor)
        try:
            os.kill(os.getpid(), signal.SIGINT)
        except Exception:
            pass


# ---------- reiniciar docker do Gitea ----------

def restart_gitea_docker() -> bool:
    """
    Tenta rodar 'docker compose restart' na pasta doker/getea.
    Retorna True se aparentemente deu certo, False se falhou.
    """
    gitea_dir = get_base_dir() / "doker" / "getea"

    try:
        subprocess.run(
            ["docker", "compose", "restart"],
            cwd=str(gitea_dir),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return True
    except Exception:
        return False
