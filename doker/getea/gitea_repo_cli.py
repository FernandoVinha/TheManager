# getea/gitea_repo_cli.py
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional, Tuple

ENV_FILENAME = ".env"

# =======================
# Utilidades de ambiente
# =======================

def _strip_quotes(v: str) -> str:
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    return v

def load_env_or_die() -> dict:
    """
    Lê .env do diretório atual.
    Aceita linhas no formato KEY=VAL (ignora comentários e linhas vazias).
    """
    path = os.path.join(os.getcwd(), ENV_FILENAME)
    if not os.path.isfile(path):
        raise RuntimeError(f"File {ENV_FILENAME} not found in {os.getcwd()}")
    env: dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = _strip_quotes(v.strip())
    return env

def base_url_and_token() -> Tuple[str, str]:
    """
    Retorna (base_url, admin_token) a partir do .env local.
    Usa ROOT_URL como fallback de GITEA_BASE_URL.
    """
    env = load_env_or_die()
    base_url = (env.get("ROOT_URL") or env.get("GITEA_BASE_URL") or "").rstrip("/")
    token = env.get("GITEA_ADMIN_TOKEN", "")
    if not base_url:
        raise RuntimeError("Define ROOT_URL or GITEA_BASE_URL in .env")
    if not token:
        raise RuntimeError("Define GITEA_ADMIN_TOKEN in .env")
    return base_url, token

# =======================
# HTTP helpers
# =======================

def http(method: str, url: str, token: str, *, sudo: str = "", payload: dict | None = None, timeout: int = 25):
    """
    Faz a requisição HTTP à API do Gitea.
    - method: GET|POST|PATCH|PUT|DELETE
    - token: token do admin (ou outro com permissão)
    - sudo: se informado, age como esse usuário/org (header 'Sudo')
    - payload: dicionário JSON opcional
    Retorna JSON (dict/list) quando Content-Type é application/json; caso contrário, texto.
    Lança urllib.error.HTTPError em erro HTTP.
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
        if body and resp.headers.get("Content-Type", "").startswith("application/json"):
            return json.loads(body)
        return body

def print_json(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))

def _resolve_owner_kind(base: str, tok: str, owner: str) -> str:
    """
    Retorna 'user' ou 'org' verificando os endpoints adequados.
    Lança erro se não existir.
    """
    u = f"{base}/api/v1/users/{urllib.parse.quote(owner)}"
    o = f"{base}/api/v1/orgs/{urllib.parse.quote(owner)}"
    try:
        http("GET", u, tok)
        return "user"
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    try:
        http("GET", o, tok)
        return "org"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError(f"Owner '{owner}' does not exist as a user or organization in Gitea.")
        raise

# =======================
# Operações de repositório
# =======================

def op_show(owner: str, repo: str):
    base, tok = base_url_and_token()
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}"
    return http("GET", url, tok)

def op_list(owner: str, *, page: Optional[int] = None, limit: Optional[int] = None):
    """
    Lista repositórios do owner (usuário/org) usando endpoints públicos:
      - /api/v1/users/{u}/repos ou /api/v1/orgs/{o}/repos
    Suporta paginação ?page=&limit= quando fornecidos.
    """
    base, tok = base_url_and_token()
    kind = _resolve_owner_kind(base, tok, owner)
    if kind == "user":
        url = f"{base}/api/v1/users/{urllib.parse.quote(owner)}/repos"
    else:
        url = f"{base}/api/v1/orgs/{urllib.parse.quote(owner)}/repos"

    qs: list[tuple[str, str]] = []
    if page is not None:
        qs.append(("page", str(page)))
    if limit is not None:
        qs.append(("limit", str(limit)))
    if qs:
        url = f"{url}?{urllib.parse.urlencode(qs)}"

    return http("GET", url, tok)

def op_create(owner: str, name: str, *, desc: str | None, private: str | None,
              default_branch: str | None, auto_init: bool, gitign: str | None, license_: str | None):
    """
    Cria repo sob 'owner' via /api/v1/user/repos + header Sudo.
    Idempotente: se retornar 409 (já existe), faz GET do repo e retorna o estado atual.
    """
    base, tok = base_url_and_token()
    payload: dict[str, object] = {"name": name}
    if desc is not None:
        payload["description"] = desc
    if private is not None:
        pv = private.lower()
        if pv not in ("true", "false"):
            raise RuntimeError("--private must be true|false")
        payload["private"] = (pv == "true")
    if default_branch:
        payload["default_branch"] = default_branch
    if auto_init:
        payload["auto_init"] = True
    if gitign:
        payload["gitignores"] = gitign
    if license_:
        payload["license"] = license_

    url = f"{base}/api/v1/user/repos"
    try:
        return http("POST", url, tok, sudo=owner, payload=payload)
    except urllib.error.HTTPError as e:
        if e.code != 409:
            raise
        # Já existe: retorna o repo atual
        show_url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}"
        return http("GET", show_url, tok)

def op_edit(owner: str, repo: str, *, new_name: str | None, desc: str | None, private: str | None,
            default_branch: str | None, archived: str | None):
    base, tok = base_url_and_token()
    payload: dict[str, object] = {}
    if new_name:
        payload["name"] = new_name
    if desc is not None:
        payload["description"] = desc
    if private is not None:
        pv = private.lower()
        if pv not in ("true", "false"):
            raise RuntimeError("--private must be true|false")
        payload["private"] = (pv == "true")
    if default_branch:
        payload["default_branch"] = default_branch
    if archived is not None:
        av = archived.lower()
        if av not in ("true", "false"):
            raise RuntimeError("--archived must be true|false")
        payload["archived"] = (av == "true")
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}"
    return http("PATCH", url, tok, payload=payload)

def op_delete(owner: str, repo: str):
    base, tok = base_url_and_token()
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}"
    return http("DELETE", url, tok)

def op_fork(src_owner: str, src_repo: str, *, dst_owner: str | None, name: str | None):
    """
    Faz fork de {src_owner}/{src_repo}.
    Se dst_owner for informado, usa header Sudo para criar o fork no namespace dele.
    """
    base, tok = base_url_and_token()
    payload: dict[str, object] = {}
    if name:
        payload["name"] = name
    sudo = dst_owner or ""  # se vazio, cai na conta do dono do token
    url = f"{base}/api/v1/repos/{urllib.parse.quote(src_owner)}/{urllib.parse.quote(src_repo)}/forks"
    return http("POST", url, tok, sudo=sudo, payload=payload)

def op_pr_create(owner: str, repo: str, *, head: str, base_branch: str, title: str, body: str | None):
    base, tok = base_url_and_token()
    payload: dict[str, object] = {"head": head, "base": base_branch, "title": title}
    if body:
        payload["body"] = body
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/pulls"
    return http("POST", url, tok, payload=payload)

def op_pr_merge(owner: str, repo: str, *, index: int, method: str | None, title: str | None, message: str | None, delete_branch: str | None):
    base, tok = base_url_and_token()
    payload: dict[str, object] = {}
    if method:
        mm = method.lower()
        if mm not in ("merge", "rebase", "squash", "rebase-merge"):
            raise RuntimeError("--method must be merge|rebase|squash|rebase-merge")
        payload["Do"] = mm
    if title:
        payload["MergeTitleField"] = title
    if message:
        payload["MergeMessageField"] = message
    if delete_branch is not None:
        dv = delete_branch.lower()
        if dv not in ("true", "false"):
            raise RuntimeError("--delete-branch must be true|false")
        payload["delete_branch_after_merge"] = (dv == "true")
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/pulls/{index}/merge"
    return http("POST", url, tok, payload=payload)

def op_collab_add(owner: str, repo: str, user: str, perm: str | None):
    """
    Adiciona colaborador (perm: read|write|admin). Valida entrada.
    """
    base, tok = base_url_and_token()
    if perm:
        p = perm.lower()
        if p not in ("read", "write", "admin"):
            raise RuntimeError("--perm must be one of: read|write|admin")
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/collaborators/{urllib.parse.quote(user)}"
    payload = {"permission": perm} if perm else {}
    return http("PUT", url, tok, payload=payload)

def op_collab_del(owner: str, repo: str, user: str):
    base, tok = base_url_and_token()
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/collaborators/{urllib.parse.quote(user)}"
    return http("DELETE", url, tok)

def op_branches(owner: str, repo: str):
    base, tok = base_url_and_token()
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/branches"
    return http("GET", url, tok)

def op_prs(owner: str, repo: str):
    base, tok = base_url_and_token()
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/pulls"
    return http("GET", url, tok)

# =======================
# CLI
# =======================

def main():
    p = argparse.ArgumentParser(description="Gitea Repo CLI (.env in current directory)")
    sub = p.add_subparsers(dest="cmd", required=True)

    # show
    s = sub.add_parser("show", help="Show repository")
    s.add_argument("--owner", required=True)
    s.add_argument("--repo", required=True)

    # list
    l = sub.add_parser("list", help="List repositories for owner (users/orgs endpoints)")
    l.add_argument("--owner", required=True)
    l.add_argument("--page", type=int)
    l.add_argument("--limit", type=int)

    # create
    c = sub.add_parser("create", help="Create repository under owner (via Sudo)")
    c.add_argument("--owner", required=True, help="user/org where the repo will be created")
    c.add_argument("--name", required=True)
    c.add_argument("--desc")
    c.add_argument("--private", help="true|false")
    c.add_argument("--default-branch")
    c.add_argument("--auto-init", action="store_true", help="create initial README")
    c.add_argument("--gitign", help="gitignore template (e.g., Python)")
    c.add_argument("--license", dest="license_", help="license template (e.g., MIT)")

    # edit
    e = sub.add_parser("edit", help="Edit repository")
    e.add_argument("--owner", required=True)
    e.add_argument("--repo", required=True)
    e.add_argument("--new-name")
    e.add_argument("--desc")
    e.add_argument("--private", help="true|false")
    e.add_argument("--default-branch")
    e.add_argument("--archived", help="true|false")

    # delete
    d = sub.add_parser("delete", help="Delete repository")
    d.add_argument("--owner", required=True)
    d.add_argument("--repo", required=True)

    # fork
    f = sub.add_parser("fork", help="Fork repository")
    f.add_argument("--src-owner", required=True)
    f.add_argument("--src-repo", required=True)
    f.add_argument("--dst-owner", help="who receives the fork (Sudo)")
    f.add_argument("--name", help="fork name (optional)")

    # PR create
    pc = sub.add_parser("pr-create", help="Create Pull Request")
    pc.add_argument("--owner", required=True)
    pc.add_argument("--repo", required=True)
    pc.add_argument("--head", required=True, help="branch with changes (e.g., feature)")
    pc.add_argument("--base", dest="base_branch", required=True, help="target branch (e.g., main)")
    pc.add_argument("--title", required=True)
    pc.add_argument("--body")

    # PR merge
    pm = sub.add_parser("pr-merge", help="Merge Pull Request")
    pm.add_argument("--owner", required=True)
    pm.add_argument("--repo", required=True)
    pm.add_argument("--index", required=True, type=int, help="PR number/ID")
    pm.add_argument("--method", help="merge|rebase|squash|rebase-merge")
    pm.add_argument("--title")
    pm.add_argument("--message")
    pm.add_argument("--delete-branch", help="true|false")

    # collaborators
    ca = sub.add_parser("collab-add", help="Add collaborator")
    ca.add_argument("--owner", required=True)
    ca.add_argument("--repo", required=True)
    ca.add_argument("--user", required=True)
    ca.add_argument("--perm", choices=["read", "write", "admin"], help="permission")

    cd = sub.add_parser("collab-del", help="Remove collaborator")
    cd.add_argument("--owner", required=True)
    cd.add_argument("--repo", required=True)
    cd.add_argument("--user", required=True)

    # branches
    b = sub.add_parser("branches", help="List branches")
    b.add_argument("--owner", required=True)
    b.add_argument("--repo", required=True)

    # prs list
    prl = sub.add_parser("prs", help="List pull requests")
    prl.add_argument("--owner", required=True)
    prl.add_argument("--repo", required=True)

    args = p.parse_args()

    try:
        if args.cmd == "show":
            print_json(op_show(args.owner, args.repo))

        elif args.cmd == "list":
            print_json(op_list(args.owner, page=args.page, limit=args.limit))

        elif args.cmd == "create":
            res = op_create(args.owner, args.name,
                            desc=args.desc,
                            private=args.private,
                            default_branch=args.default_branch,
                            auto_init=args.auto_init,
                            gitign=args.gitign,
                            license_=args.license_)
            print_json(res)

        elif args.cmd == "edit":
            res = op_edit(args.owner, args.repo,
                          new_name=args.new_name,
                          desc=args.desc,
                          private=args.private,
                          default_branch=args.default_branch,
                          archived=args.archived)
            print_json(res)

        elif args.cmd == "delete":
            op_delete(args.owner, args.repo)
            print("✅ Repository deleted.")

        elif args.cmd == "fork":
            res = op_fork(args.src_owner, args.src_repo, dst_owner=args.dst_owner, name=args.name)
            print_json(res)

        elif args.cmd == "pr-create":
            res = op_pr_create(args.owner, args.repo,
                               head=args.head, base_branch=args.base_branch,
                               title=args.title, body=args.body)
            print_json(res)

        elif args.cmd == "pr-merge":
            res = op_pr_merge(args.owner, args.repo,
                              index=args.index, method=args.method,
                              title=args.title, message=args.message,
                              delete_branch=args.delete_branch)
            print_json(res)

        elif args.cmd == "collab-add":
            res = op_collab_add(args.owner, args.repo, args.user, args.perm)
            print_json(res)

        elif args.cmd == "collab-del":
            op_collab_del(args.owner, args.repo, args.user)
            print("✅ Collaborator removed.")

        elif args.cmd == "branches":
            print_json(op_branches(args.owner, args.repo))

        elif args.cmd == "prs":
            print_json(op_prs(args.owner, args.repo))

        else:
            raise RuntimeError("Invalid command")

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"❌ HTTP {e.code} {e.reason} — {body}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
