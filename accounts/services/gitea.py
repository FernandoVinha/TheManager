# accounts/services/gitea.py
from __future__ import annotations

import json
import os
import sys
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from django.conf import settings


# =========================
#  Config / HTTP helpers
# =========================

@dataclass
class GiteaConfig:
    base_url: str
    admin_token: str

    @classmethod
    def from_settings(cls) -> "GiteaConfig":
        """
        Carrega config a partir do settings/env.
        Aceita fallback ROOT_URL se GITEA_BASE_URL não existir.
        """
        base = (
            getattr(settings, "GITEA_BASE_URL", None)
            or os.getenv("GITEA_BASE_URL")
            or getattr(settings, "ROOT_URL", None)
            or os.getenv("ROOT_URL")
        )
        token = getattr(settings, "GITEA_ADMIN_TOKEN", None) or os.getenv("GITEA_ADMIN_TOKEN")

        if not base:
            raise RuntimeError("GITEA_BASE_URL/ROOT_URL não configurado")
        if not token:
            raise RuntimeError("GITEA_ADMIN_TOKEN não configurado")

        return cls(base.rstrip("/"), token)


def _http(
    method: str,
    url: str,
    token: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 20,
) -> Any:
    """
    Requisição HTTP simples com token admin no header.
    Retorna JSON (dict/list) se houver corpo; senão None.
    Lança urllib.error.HTTPError em caso de HTTP != 2xx.
    """
    data: Optional[bytes] = None
    req = urllib.request.Request(url, method=method.upper())
    req.add_header("Accept", "application/json")
    req.add_header("Authorization", f"token {token}")

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        data = body
        req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw) if raw else None




def create_user(
    *,
    username: str,
    email: Optional[str],
    password: str,
    is_admin: bool = False,
    must_change_password: bool = False,
    visibility: Optional[str] = None,
    full_name: Optional[str] = None,
    max_repo_creation: Optional[int] = None,
    allow_create_organization: Optional[bool] = None,
    restricted: Optional[bool] = None,
    prohibit_login: Optional[bool] = None,
    website: Optional[str] = None,
    location: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    POST /api/v1/admin/users
    Cria usuário e retorna o user público (GET /users/{username}) para normalizar.
    """
    cfg = GiteaConfig.from_settings()
    url = f"{cfg.base_url}/api/v1/admin/users"

    payload: Dict[str, Any] = {
        "username": username,
        "password": password,
        "email": email or "",
        "must_change_password": bool(must_change_password),
        "send_notify": False,
    }
    if is_admin:
        payload["admin"] = True
    if visibility:
        payload["visibility"] = visibility
    if full_name:
        payload["full_name"] = full_name
    if max_repo_creation is not None:
        payload["max_repo_creation"] = int(max_repo_creation)
    if allow_create_organization is not None:
        payload["allow_create_organization"] = bool(allow_create_organization)
    if restricted is not None:
        payload["restricted"] = bool(restricted)
    if prohibit_login is not None:
        payload["prohibit_login"] = bool(prohibit_login)
    if website:
        payload["website"] = website
    if location:
        payload["location"] = location
    if description:
        payload["description"] = description

    _http("POST", url, cfg.admin_token, payload)

    # normaliza pegando a representação pública
    pub = _http("GET", f"{cfg.base_url}/api/v1/users/{urllib.parse.quote(username)}", cfg.admin_token)
    if isinstance(pub, dict):
        return pub
    return {"login": username, "email": email, "is_admin": is_admin}


def rename_user(*, old_username: str, new_username: str) -> None:
    """
    POST /api/v1/admin/users/{username}/rename
    """
    cfg = GiteaConfig.from_settings()
    url = f"{cfg.base_url}/api/v1/admin/users/{urllib.parse.quote(old_username)}/rename"
    _http("POST", url, cfg.admin_token, {"new_username": new_username})


def patch_user(
    *,
    username: str,
    email: Optional[str] = None,
    is_admin: Optional[bool] = None,
    full_name: Optional[str] = None,
    website: Optional[str] = None,
    location: Optional[str] = None,
    description: Optional[str] = None,
    visibility: Optional[str] = None,
    max_repo_creation: Optional[int] = None,
) -> Dict[str, Any]:
    """
    PATCH /api/v1/admin/users/{username}
    Envia apenas campos fornecidos. Retorna user atualizado (ou dict vazio/None).
    """
    cfg = GiteaConfig.from_settings()
    url = f"{cfg.base_url}/api/v1/admin/users/{urllib.parse.quote(username)}"

    payload: Dict[str, Any] = {}
    if email is not None:
        payload["email"] = email
    if is_admin is not None:
        payload["admin"] = bool(is_admin)
    if full_name is not None:
        payload["full_name"] = full_name
    if website is not None:
        payload["website"] = website
    if location is not None:
        payload["location"] = location
    if description is not None:
        payload["description"] = description
    if visibility is not None:
        payload["visibility"] = visibility
    if max_repo_creation is not None:
        payload["max_repo_creation"] = int(max_repo_creation)

    if not payload:
        # Nada a fazer
        return {}

    updated = _http("PATCH", url, cfg.admin_token, payload)

    # Algumas instalações retornam {} no PATCH; tente ler o público
    if not updated or not isinstance(updated, dict):
        updated = _http("GET", f"{cfg.base_url}/api/v1/users/{urllib.parse.quote(username)}", cfg.admin_token)
        if not isinstance(updated, dict):
            updated = {}
    return updated


def delete_user(*, username: str, purge: bool = False) -> None:
    """
    DELETE /api/v1/admin/users/{username}
    - purge=False (default) mantém histórico/commits (fica como 'Ghost')
    """
    cfg = GiteaConfig.from_settings()
    # Em versões recentes, o 'purge' pode ser query param suportado:
    url = f"{cfg.base_url}/api/v1/admin/users/{urllib.parse.quote(username)}"
    if purge:
        url += "?purge=true"
    _http("DELETE", url, cfg.admin_token)


def list_users(*, page: int = 1, limit: int = 50, query: Optional[str] = None) -> Dict[str, Any]:
    """
    GET /api/v1/admin/users?limit=50&page=1&search=abc
    Retorna:
      {
        "results": [ { "id":..., "login":..., "email":..., "full_name":..., "avatar_url":..., "is_admin":... }, ... ],
        "total": <int ou 0 se desconhecido>
      }
    """
    cfg = GiteaConfig.from_settings()
    params = [f"limit={int(limit)}", f"page={int(page)}"]
    if query:
        params.append("search=" + urllib.parse.quote(query))
    url = f"{cfg.base_url}/api/v1/admin/users"
    if params:
        url += "?" + "&".join(params)

    raw = _http("GET", url, cfg.admin_token)
    results = []
    total = 0

    # A API normalmente retorna lista; alguns forks retornam dict com data/total
    if isinstance(raw, list):
        results = raw
    elif isinstance(raw, dict):
        if "data" in raw and isinstance(raw["data"], list):
            results = raw["data"]
        elif "results" in raw and isinstance(raw["results"], list):
            results = raw["results"]
        total = int(raw.get("total", 0) or 0)

    norm = []
    for u in results:
        norm.append(
            {
                "id": u.get("id"),
                "login": u.get("login") or u.get("username"),
                "email": u.get("email"),
                "full_name": u.get("full_name") or "",
                "avatar_url": u.get("avatar_url"),
                "is_admin": bool(u.get("is_admin", False)),
            }
        )

    return {"results": norm, "total": total}


# =========================
#  Password via CLI
# =========================

def change_password(*, username: str, new_password: str) -> None:
    """
    Troca a senha do usuário via CLI local (getea/gitea_user_cli.py),
    executando com cwd= getea/ para que ele encontre o .env nesse diretório.

    Requer:
      - TheManager/getea/gitea_user_cli.py   (presente)
      - TheManager/getea/.env                 (com GITEA_BASE_URL/GITEA_ADMIN_TOKEN)
    """
    # BASE_DIR do Django
    base_dir = Path(getattr(settings, "BASE_DIR", Path(__file__).resolve().parents[3]))
    getea_dir = base_dir / "getea"
    cli = getea_dir / "gitea_user_cli.py"

    if not cli.exists():
        raise FileNotFoundError(f"CLI não encontrado: {cli}")

    # Usa o mesmo Python em execução (evita PATH estranho)
    cmd = [
        sys.executable,
        str(cli),
        "edit",
        "--username", username,
        "--password", new_password,
    ]

    rc = subprocess.run(cmd, cwd=getea_dir).returncode
    if rc != 0:
        from subprocess import CalledProcessError
        raise CalledProcessError(rc, "gitea_user_cli.py edit --password …")
