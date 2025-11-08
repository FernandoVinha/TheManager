# projects/services/gitea.py
from __future__ import annotations

"""
Integração com a API do Gitea (sem dependências externas).

Principais pontos:
- Lê GITEA_BASE_URL e GITEA_ADMIN_TOKEN do settings.
- Suporta owner sendo USUÁRIO ou ORGANIZAÇÃO (ensure_owner_exists / get_owner_kind).
- Criação de repositório via POST /user/repos com header "Sudo: <owner>".
- Adição/remoção de colaboradores e deleção de repositório.
- Rotinas síncronas usando urllib.* (sem requests).

Observações:
- Use estas funções a partir de transações Django com transaction.on_commit(...)
  quando forem chamadas dentro de signals, para evitar inconsistências.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

from django.conf import settings


# =========================
# Config & HTTP helpers
# =========================

def _base_and_token() -> Tuple[str, str]:
    """
    Lê GITEA_BASE_URL e GITEA_ADMIN_TOKEN do settings.
    """
    base = (getattr(settings, "GITEA_BASE_URL", "") or "").rstrip("/")
    token = getattr(settings, "GITEA_ADMIN_TOKEN", "")
    if not base:
        raise RuntimeError("GITEA_BASE_URL is not configured in settings.")
    if not token:
        raise RuntimeError("GITEA_ADMIN_TOKEN is not configured in settings.")
    return base, token


def _request(
    method: str,
    url: str,
    *,
    token: str,
    sudo: str = "",
    payload: Optional[dict] = None,
    timeout: int = 25,
) -> Any:
    """
    Faz uma requisição HTTP para a API do Gitea.
    - method: GET|POST|PATCH|PUT|DELETE
    - token: token de admin (ou outro com permissão suficiente)
    - sudo: quando preenchido, atua como esse usuário/org (header 'Sudo')
    - payload: dicionário JSON opcional
    """
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"token {token}"
    if sudo:
        headers["Sudo"] = sudo  # suportado para admin tokens

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace") or ""
        ctype = resp.headers.get("Content-Type", "")
        if body and ctype.startswith("application/json"):
            return json.loads(body)
        return body


def _q(s: str) -> str:
    """Atalho para quote em path segments."""
    return urllib.parse.quote(s, safe="")


# =========================
# Owner helpers (user/org)
# =========================

def get_owner_kind(owner: str) -> str:
    """
    Retorna 'user' ou 'org' para o owner informado.
    Lança erro se não existir.
    """
    base, token = _base_and_token()
    u_url = f"{base}/api/v1/users/{_q(owner)}"
    o_url = f"{base}/api/v1/orgs/{_q(owner)}"
    # tenta usuário
    try:
        _request("GET", u_url, token=token)
        return "user"
    except urllib.error.HTTPError as e_u:
        if e_u.code != 404:
            raise
    # tenta organização
    try:
        _request("GET", o_url, token=token)
        return "org"
    except urllib.error.HTTPError as e_o:
        if e_o.code == 404:
            raise RuntimeError(f"Gitea owner '{owner}' does not exist (user nor org).")
        raise


def ensure_owner_exists(owner: str) -> Dict[str, Any]:
    """
    Garante que o owner exista como usuário OU organização.
    Retorna o JSON do recurso encontrado.
    """
    base, token = _base_and_token()
    u_url = f"{base}/api/v1/users/{_q(owner)}"
    o_url = f"{base}/api/v1/orgs/{_q(owner)}"
    try:
        return _request("GET", u_url, token=token)
    except urllib.error.HTTPError as e_u:
        if e_u.code != 404:
            raise
        try:
            return _request("GET", o_url, token=token)
        except urllib.error.HTTPError as e_o:
            if e_o.code == 404:
                raise RuntimeError(f"Gitea owner '{owner}' does not exist (user nor org).")
            raise


# =========================
# Repository operations
# =========================

def create_repo(
    owner: str,
    name: str,
    *,
    description: str = "",
    private: bool = True,
    default_branch: str = "main",
    auto_init: bool = True,
    license_template: str | None = None,
    gitignore: str | None = None,
) -> Dict[str, Any]:
    """
    Cria um repositório no owner (usuário/org) via Sudo header.
    Implementação: POST /api/v1/user/repos com 'Sudo: <owner>'
    """
    base, token = _base_and_token()
    payload: Dict[str, Any] = {
        "name": name,
        "description": description or "",
        "private": bool(private),
        "default_branch": default_branch or "main",
        "auto_init": bool(auto_init),
    }
    if license_template:
        payload["license"] = license_template
    if gitignore:
        payload["gitignores"] = gitignore

    url = f"{base}/api/v1/user/repos"
    return _request("POST", url, token=token, sudo=owner, payload=payload)


def delete_repo(owner: str, repo: str) -> Any:
    """
    Deleta um repositório.
    Implementação: DELETE /api/v1/repos/{owner}/{repo}
    """
    base, token = _base_and_token()
    url = f"{base}/api/v1/repos/{_q(owner)}/{_q(repo)}"
    return _request("DELETE", url, token=token)


def add_collaborator(owner: str, repo: str, username: str, permission: str = "write") -> Any:
    """
    Adiciona colaborador ao repositório com uma permissão (read|write|admin).
    Implementação: PUT /api/v1/repos/{owner}/{repo}/collaborators/{username}
    Body: { "permission": "write" }
    """
    base, token = _base_and_token()
    url = f"{base}/api/v1/repos/{_q(owner)}/{_q(repo)}/collaborators/{_q(username)}"
    payload = {"permission": permission}
    return _request("PUT", url, token=token, payload=payload)


def remove_collaborator(owner: str, repo: str, username: str) -> Any:
    """
    Remove colaborador do repositório.
    Implementação: DELETE /api/v1/repos/{owner}/{repo}/collaborators/{username}
    """
    base, token = _base_and_token()
    url = f"{base}/api/v1/repos/{_q(owner)}/{_q(repo)}/collaborators/{_q(username)}"
    return _request("DELETE", url, token=token)


def repo_web_url(owner: str, repo: str) -> str:
    """
    Monta a URL web do repositório.
    """
    base, _ = _base_and_token()
    return f"{base}/{owner}/{repo}"
