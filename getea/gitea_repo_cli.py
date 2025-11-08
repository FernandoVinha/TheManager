#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gitea_repo_cli.py
CLI para operações de repositório no Gitea usando a API:

- Lê SEMPRE o .env do diretório atual (ROOT_URL/GITEA_BASE_URL e GITEA_ADMIN_TOKEN)
- Usa header "Sudo: <owner>" p/ agir como um usuário/organização (ex.: criar repo em 'owner')
- Subcomandos:
    create       -> cria repo (em owner via --owner usando Sudo)
    edit         -> edita repo (descrição, private, default_branch, etc.)
    delete       -> apaga repo
    show         -> mostra repo (JSON)
    list         -> lista repos do owner (usuário/org) **sem Sudo** (endpoint users/orgs)
    fork         -> faz fork de repo em outro owner (via Sudo)
    pr-create    -> abre Pull Request
    pr-merge     -> faz merge de PR
    collab-add   -> adiciona colaborador
    collab-del   -> remove colaborador
    branches     -> lista branches do repo
    prs          -> lista PRs do repo

Exemplos:
  python gitea_repo_cli.py create --owner john --name demo --private true --desc "meu repo"
  python gitea_repo_cli.py edit   --owner john --repo demo --desc "novo texto" --default-branch main
  python gitea_repo_cli.py delete --owner john --repo demo
  python gitea_repo_cli.py fork   --src-owner john --src-repo demo --dst-owner manager --name demo-fork
  python gitea_repo_cli.py pr-create --owner john --repo demo --head feature --base main --title "Add X"
  python gitea_repo_cli.py pr-merge  --owner john --repo demo --index 3 --method merge
  python gitea_repo_cli.py collab-add --owner john --repo demo --user maria --perm write
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional

ENV_FILENAME = ".env"

# =============== utils ===============
def _strip_quotes(v: str) -> str:
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    return v

def load_env_or_die() -> dict:
    path = os.path.join(os.getcwd(), ENV_FILENAME)
    if not os.path.isfile(path):
        raise RuntimeError(f"Arquivo {ENV_FILENAME} não encontrado em {os.getcwd()}")
    env = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = _strip_quotes(v.strip())
    return env

def base_url_and_token() -> tuple[str, str]:
    env = load_env_or_die()
    base_url = (env.get("ROOT_URL") or env.get("GITEA_BASE_URL") or "").rstrip("/")
    token = env.get("GITEA_ADMIN_TOKEN", "")
    if not base_url:
        raise RuntimeError("Defina ROOT_URL ou GITEA_BASE_URL no .env")
    if not token:
        raise RuntimeError("Defina GITEA_ADMIN_TOKEN no .env")
    return base_url, token

def http(method: str, url: str, token: str, *, sudo: str = "", payload: dict | None = None, timeout: int = 25):
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
    Levanta exceção se nenhum dos dois existir.
    """
    u = f"{base}/api/v1/users/{urllib.parse.quote(owner)}"
    o = f"{base}/api/v1/orgs/{urllib.parse.quote(owner)}"
    try:
        http("GET", u, tok)
        return "user"
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    # tenta org
    try:
        http("GET", o, tok)
        return "org"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError(f"Owner '{owner}' não existe como usuário nem organização no Gitea.")
        raise

# =============== ops ===============
def op_show(owner: str, repo: str):
    base, tok = base_url_and_token()
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}"
    return http("GET", url, tok)

def op_list(owner: str, *, page: Optional[int] = None, limit: Optional[int] = None):
    """
    Lista repos do owner sem usar Sudo, escolhendo /users/{u}/repos ou /orgs/{o}/repos.
    Suporta paginação via ?page=&limit= se informado.
    """
    base, tok = base_url_and_token()
    kind = _resolve_owner_kind(base, tok, owner)
    if kind == "user":
        url = f"{base}/api/v1/users/{urllib.parse.quote(owner)}/repos"
    else:
        url = f"{base}/api/v1/orgs/{urllib.parse.quote(owner)}/repos"

    qs = []
    if page is not None:
        qs.append(("page", str(page)))
    if limit is not None:
        qs.append(("limit", str(limit)))
    if qs:
        url = f"{url}?{urllib.parse.urlencode(qs)}"

    return http("GET", url, tok)

def op_create(owner: str, name: str, *, desc: str | None, private: str | None,
              default_branch: str | None, auto_init: bool, gitign: str | None, license_: str | None):
    base, tok = base_url_and_token()
    payload = {"name": name}
    if desc is not None:
        payload["description"] = desc
    if private is not None:
        pv = private.lower()
        if pv not in ("true", "false"):
            raise RuntimeError("--private deve ser true|false")
        payload["private"] = (pv == "true")
    if default_branch:
        payload["default_branch"] = default_branch
    if auto_init:
        payload["auto_init"] = True
    if gitign:
        payload["gitignores"] = gitign
    if license_:
        payload["license"] = license_

    # Cria no "owner" usando Sudo e /user/repos (funciona para user e org)
    url = f"{base}/api/v1/user/repos"
    return http("POST", url, tok, sudo=owner, payload=payload)

def op_edit(owner: str, repo: str, *, new_name: str | None, desc: str | None, private: str | None,
            default_branch: str | None, archived: str | None):
    base, tok = base_url_and_token()
    payload = {}
    if new_name:
        payload["name"] = new_name
    if desc is not None:
        payload["description"] = desc
    if private is not None:
        pv = private.lower()
        if pv not in ("true", "false"):
            raise RuntimeError("--private deve ser true|false")
        payload["private"] = (pv == "true")
    if default_branch:
        payload["default_branch"] = default_branch
    if archived is not None:
        av = archived.lower()
        if av not in ("true", "false"):
            raise RuntimeError("--archived deve ser true|false")
        payload["archived"] = (av == "true")
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}"
    return http("PATCH", url, tok, payload=payload)

def op_delete(owner: str, repo: str):
    base, tok = base_url_and_token()
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}"
    return http("DELETE", url, tok)

def op_fork(src_owner: str, src_repo: str, *, dst_owner: str | None, name: str | None):
    # Faz fork do repo (Sudo=dst_owner p/ cair na conta do “destino”)
    base, tok = base_url_and_token()
    payload = {}
    if name:
        payload["name"] = name
    sudo = dst_owner or ""  # se não enviar, cai na conta do token admin
    url = f"{base}/api/v1/repos/{urllib.parse.quote(src_owner)}/{urllib.parse.quote(src_repo)}/forks"
    return http("POST", url, tok, sudo=sudo, payload=payload)

def op_pr_create(owner: str, repo: str, *, head: str, base_branch: str, title: str, body: str | None):
    base, tok = base_url_and_token()
    payload = {"head": head, "base": base_branch, "title": title}
    if body:
        payload["body"] = body
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/pulls"
    return http("POST", url, tok, payload=payload)

def op_pr_merge(owner: str, repo: str, *, index: int, method: str | None, title: str | None, message: str | None, delete_branch: str | None):
    base, tok = base_url_and_token()
    payload = {}
    if method:
        mm = method.lower()
        if mm not in ("merge", "rebase", "squash", "rebase-merge"):
            raise RuntimeError("--method deve ser merge|rebase|squash|rebase-merge")
        payload["Do"] = mm
    if title:
        payload["MergeTitleField"] = title
    if message:
        payload["MergeMessageField"] = message
    if delete_branch is not None:
        dv = delete_branch.lower()
        if dv not in ("true", "false"):
            raise RuntimeError("--delete-branch deve ser true|false")
        payload["delete_branch_after_merge"] = (dv == "true")
    url = f"{base}/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}/pulls/{index}/merge"
    return http("POST", url, tok, payload=payload)

def op_collab_add(owner: str, repo: str, user: str, perm: str | None):
    base, tok = base_url_and_token()
    # perm: read|write|admin
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

# =============== CLI ===============
def main():
    p = argparse.ArgumentParser(description="Gitea Repo CLI (.env no diretório atual)")
    sub = p.add_subparsers(dest="cmd", required=True)

    # show
    s = sub.add_parser("show", help="Mostrar repo")
    s.add_argument("--owner", required=True)
    s.add_argument("--repo", required=True)

    # list
    l = sub.add_parser("list", help="Listar repos do owner (users/orgs endpoints)")
    l.add_argument("--owner", required=True)
    l.add_argument("--page", type=int)
    l.add_argument("--limit", type=int)

    # create
    c = sub.add_parser("create", help="Criar repo em owner (via Sudo)")
    c.add_argument("--owner", required=True, help="usuário/org onde o repo será criado")
    c.add_argument("--name", required=True)
    c.add_argument("--desc")
    c.add_argument("--private", help="true|false")
    c.add_argument("--default-branch")
    c.add_argument("--auto-init", action="store_true", help="criar README inicial")
    c.add_argument("--gitign", help="template .gitignore (ex: Python)")
    c.add_argument("--license", dest="license_", help="template licença (ex: MIT)")

    # edit
    e = sub.add_parser("edit", help="Editar repo")
    e.add_argument("--owner", required=True)
    e.add_argument("--repo", required=True)
    e.add_argument("--new-name")
    e.add_argument("--desc")
    e.add_argument("--private", help="true|false")
    e.add_argument("--default-branch")
    e.add_argument("--archived", help="true|false")

    # delete
    d = sub.add_parser("delete", help="Apagar repo")
    d.add_argument("--owner", required=True)
    d.add_argument("--repo", required=True)

    # fork
    f = sub.add_parser("fork", help="Fork de repo")
    f.add_argument("--src-owner", required=True)
    f.add_argument("--src-repo", required=True)
    f.add_argument("--dst-owner", help="para quem vai o fork (Sudo)")
    f.add_argument("--name", help="nome do fork (opcional)")

    # PR create
    pc = sub.add_parser("pr-create", help="Criar Pull Request")
    pc.add_argument("--owner", required=True)
    pc.add_argument("--repo", required=True)
    pc.add_argument("--head", required=True, help="branch com mudanças (ex: feature)")
    pc.add_argument("--base", dest="base_branch", required=True, help="branch alvo (ex: main)")
    pc.add_argument("--title", required=True)
    pc.add_argument("--body")

    # PR merge
    pm = sub.add_parser("pr-merge", help="Merge Pull Request")
    pm.add_argument("--owner", required=True)
    pm.add_argument("--repo", required=True)
    pm.add_argument("--index", required=True, type=int, help="número/ID do PR")
    pm.add_argument("--method", help="merge|rebase|squash|rebase-merge")
    pm.add_argument("--title")
    pm.add_argument("--message")
    pm.add_argument("--delete-branch", help="true|false")

    # collaborators
    ca = sub.add_parser("collab-add", help="Adicionar colaborador")
    ca.add_argument("--owner", required=True)
    ca.add_argument("--repo", required=True)
    ca.add_argument("--user", required=True)
    ca.add_argument("--perm", choices=["read", "write", "admin"], help="permissão")

    cd = sub.add_parser("collab-del", help="Remover colaborador")
    cd.add_argument("--owner", required=True)
    cd.add_argument("--repo", required=True)
    cd.add_argument("--user", required=True)

    # branches
    b = sub.add_parser("branches", help="Listar branches")
    b.add_argument("--owner", required=True)
    b.add_argument("--repo", required=True)

    # prs list
    prl = sub.add_parser("prs", help="Listar PRs")
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
            print("✅ Repositório deletado.")

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
            print("✅ Colaborador removido.")

        elif args.cmd == "branches":
            print_json(op_branches(args.owner, args.repo))

        elif args.cmd == "prs":
            print_json(op_prs(args.owner, args.repo))

        else:
            raise RuntimeError("Comando inválido")

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"❌ HTTP {e.code} {e.reason} — {body}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"❌ Erro: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
