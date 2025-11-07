from __future__ import annotations
import json, urllib.request, urllib.parse, urllib.error
from typing import Any, Dict, Optional
from django.conf import settings

def _base_and_token() -> tuple[str, str]:
    base = (getattr(settings, "GITEA_BASE_URL", "") or "").rstrip("/")
    token = getattr(settings, "GITEA_ADMIN_TOKEN", "")
    if not base:
        raise RuntimeError("GITEA_BASE_URL is not configured in settings.")
    if not token:
        raise RuntimeError("GITEA_ADMIN_TOKEN is not configured in settings.")
    return base, token

def _request(method: str, url: str, *, token: str, sudo: str = "", payload: Optional[dict] = None, timeout: int = 25) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"token {token}"
    if sudo:
        headers["Sudo"] = sudo
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace") or ""
        ctype = resp.headers.get("Content-Type", "")
        if body and ctype.startswith("application/json"):
            return json.loads(body)
        return body

def ensure_user_exists(username: str) -> Dict[str, Any]:
    base, token = _base_and_token()
    url = f"{base}/api/v1/users/{urllib.parse.quote(username)}"
    try:
        return _request("GET", url, token=token)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError(f"Gitea user '{username}' does not exist.")
        raise

def create_repo(owner: str, name: str, *, description: str = "", private: bool = True,
                default_branch: str = "main", auto_init: bool = True, license_template: str | None = None,
                gitignore: str | None = None) -> Dict[str, Any]:
    base, token = _base_and_token()
    payload = {
        "name": name,
        "description": description or "",
        "private": bool(private),
        "default_branch": default_branch or "main",
        "auto_init": bool(auto_init),
    }
    if license_template: payload["license"] = license_template
    if gitignore: payload["gitignores"] = gitignore
    url = f"{base}/api/v1/user/repos"  # with Sudo=<owner> it creates under that user/org
    return _request("POST", url, token=token, sudo=owner, payload=payload)

def add_collaborator(owner: str, repo: str, username: str, permission: str = "write") -> Any:
    # permission: read|write|admin
    base, token = _base_and_token()
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/collaborators/{urllib.parse.quote(username)}"
    payload = {"permission": permission}
    return _request("PUT", url, token=token, payload=payload)

def remove_collaborator(owner: str, repo: str, username: str) -> Any:
    base, token = _base_and_token()
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/collaborators/{urllib.parse.quote(username)}"
    return _request("DELETE", url, token=token)

def delete_repo(owner: str, repo: str) -> Any:
    base, token = _base_and_token()
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}"
    return _request("DELETE", url, token=token)

def repo_web_url(owner: str, repo: str) -> str:
    base, _ = _base_and_token()
    return f"{base}/{owner}/{repo}"
