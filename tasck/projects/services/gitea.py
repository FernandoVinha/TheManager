#tasck/projects/services/gitea.py
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

from django.conf import settings


# =========================================================
# Config & HTTP helpers
# =========================================================

def _base_and_token() -> Tuple[str, str]:
    """
    Reads GITEA_BASE_URL and GITEA_ADMIN_TOKEN from Django settings (or env mirrored into settings).
    Returns (base_url, admin_token) with base_url stripped of trailing "/".
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
    Performs an HTTP request to Gitea's API.
    - method: GET|POST|PATCH|PUT|DELETE
    - token: admin (or sufficient) token
    - sudo: if provided, acts as that user/org (via 'Sudo' header)
    - payload: optional JSON dict
    Returns parsed JSON when Content-Type is application/json; otherwise returns raw text.
    Raises urllib.error.HTTPError for non-2xx responses.
    """
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


def _q(s: str) -> str:
    """URL-quote for path segments (safe='')."""
    return urllib.parse.quote(s, safe="")


# =========================================================
# Owner helpers (user/org)
# =========================================================

def get_owner_kind(owner: str) -> str:
    """
    Returns 'user' or 'org' for the provided owner.
    Raises RuntimeError if neither exists.
    """
    base, token = _base_and_token()
    u_url = f"{base}/api/v1/users/{_q(owner)}"
    o_url = f"{base}/api/v1/orgs/{_q(owner)}"

    try:
        _request("GET", u_url, token=token)
        return "user"
    except urllib.error.HTTPError as e_u:
        if e_u.code != 404:
            raise

    try:
        _request("GET", o_url, token=token)
        return "org"
    except urllib.error.HTTPError as e_o:
        if e_o.code == 404:
            raise RuntimeError(f"Gitea owner '{owner}' does not exist (user nor org).")
        raise


def ensure_owner_exists(owner: str) -> Dict[str, Any]:
    """
    Ensures the owner exists either as a user OR an organization.
    Returns the JSON for the resource found.
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


# =========================================================
# Repository operations
# =========================================================

def get_repo(owner: str, repo: str) -> Dict[str, Any]:
    base, token = _base_and_token()
    url = f"{base}/api/v1/repos/{_q(owner)}/{_q(repo)}"
    return _request("GET", url, token=token)


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
    Creates a repository under the given owner (user/org) using Sudo header:
      POST /api/v1/user/repos  (Header: Sudo=<owner>)
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
    base, token = _base_and_token()
    url = f"{base}/api/v1/repos/{_q(owner)}/{_q(repo)}"
    return _request("DELETE", url, token=token)


def add_collaborator(owner: str, repo: str, username: str, permission: str = "write") -> Any:
    base, token = _base_and_token()
    url = f"{base}/api/v1/repos/{_q(owner)}/{_q(repo)}/collaborators/{_q(username)}"
    payload = {"permission": permission}
    return _request("PUT", url, token=token, payload=payload)


def remove_collaborator(owner: str, repo: str, username: str) -> Any:
    base, token = _base_and_token()
    url = f"{base}/api/v1/repos/{_q(owner)}/{_q(repo)}/collaborators/{_q(username)}"
    return _request("DELETE", url, token=token)


def repo_web_url(owner: str, repo: str) -> str:
    base, _ = _base_and_token()
    return f"{base}/{owner}/{repo}"


def fork_repo(src_owner: str, src_repo: str, *, dst_owner: str, name: str | None = None) -> Dict[str, Any]:
    base, token = _base_and_token()
    url = f"{base}/api/v1/repos/{_q(src_owner)}/{_q(src_repo)}/forks"
    payload: Dict[str, Any] = {}
    if name:
        payload["name"] = name
    return _request("POST", url, token=token, sudo=dst_owner, payload=payload)


# =========================================================
# Pull Requests
# =========================================================

def create_pull_request(
    owner: str,
    repo: str,
    *,
    head: str,
    base_branch: str,
    title: str,
    body: str | None = None,
) -> Dict[str, Any]:
    """
    POST /api/v1/repos/{owner}/{repo}/pulls
      payload: {"head": "<fork_owner>:<branch>", "base": "<branch>", "title": "...", "body": "...?"}
    """
    base, token = _base_and_token()
    url = f"{base}/api/v1/repos/{_q(owner)}/{_q(repo)}/pulls"
    payload: Dict[str, Any] = {"head": head, "base": base_branch, "title": title}
    if body:
        payload["body"] = body
    return _request("POST", url, token=token, payload=payload)


def merge_pull_request(
    owner: str,
    repo: str,
    pr_index: int,
    *,
    method: str = "merge",
    title: str | None = None,
    message: str | None = None,
    delete_branch: bool = False,
) -> Dict[str, Any]:
    """
    POST /api/v1/repos/{owner}/{repo}/pulls/{index}/merge
      payload:
        Do: merge|rebase|squash|rebase-merge
        MergeTitleField: optional
        MergeMessageField: optional
        delete_branch_after_merge: bool
    """
    base, token = _base_and_token()
    url = f"{base}/api/v1/repos/{_q(owner)}/{_q(repo)}/pulls/{int(pr_index)}/merge"
    payload: Dict[str, Any] = {
        "Do": method or "merge",
        "delete_branch_after_merge": bool(delete_branch),
    }
    if title:
        payload["MergeTitleField"] = title
    if message:
        payload["MergeMessageField"] = message
    return _request("POST", url, token=token, payload=payload)


# =========================================================
# Commits helpers
# =========================================================

def list_commits(owner: str, repo: str, *, branch: Optional[str] = None, page: int = 1, limit: int = 50) -> list[Dict[str, Any]]:
    base, token = _base_and_token()
    url = f"{base}/api/v1/repos/{_q(owner)}/{_q(repo)}/commits"
    qs: list[tuple[str, str]] = [("page", str(page)), ("limit", str(limit))]
    if branch:
        qs.append(("sha", branch))
    url = f"{url}?{urllib.parse.urlencode(qs)}"
    res = _request("GET", url, token=token)
    return res if isinstance(res, list) else []


def get_commit(owner: str, repo: str, sha: str) -> Dict[str, Any]:
    base, token = _base_and_token()
    url = f"{base}/api/v1/repos/{_q(owner)}/{_q(repo)}/commits/{_q(sha)}"
    return _request("GET", url, token=token)
