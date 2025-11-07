#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gitea_user_cli.py
CLI para criar, editar (inclui senha), deletar e mostrar usuários do Gitea.

- Lê SEMPRE o arquivo `.env` do diretório atual (sem opção --env)
- MUTAÇÕES por CLI do container (docker exec):
    * create: gitea admin user create
    * password: gitea admin user change-password
    * delete: gitea admin user delete [--purge]
- API admin só é usada quando necessário (rename/patch/avatar)
- SHOW usa API pública (/api/v1/users/{username}) para retornar JSON

Exemplos:
  python gitea_user_cli.py create --username john --email john@example.com --password 'Pass#2025' --admin
  python gitea_user_cli.py edit   --username john --password 'NewPass#2025'
  python gitea_user_cli.py edit   --username john --new-username john1 --full-name 'John One'
  python gitea_user_cli.py delete --username john1
  python gitea_user_cli.py show   --username manager
"""

import argparse
import json
import mimetypes
import os
import shlex
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

ENV_FILENAME = ".env"

# ------------- .env loader -------------
def load_env_or_die() -> dict:
    """Lê .env do diretório atual. Erra se não existir."""
    path = os.path.join(os.getcwd(), ENV_FILENAME)
    if not os.path.isfile(path):
        raise RuntimeError(f"Arquivo {ENV_FILENAME} não encontrado no diretório atual: {os.getcwd()}")
    env = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env

def run(cmd: str) -> int:
    proc = subprocess.run(cmd, shell=True)
    return proc.returncode

# ------------- HTTP helpers -------------
def http_get_json(url: str, token: str = "", timeout: int = 20):
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", f"token {token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read().decode("utf-8", errors="replace")
        return json.loads(data) if data else {}

def http_patch_json(url: str, token: str, payload: dict, timeout: int = 20):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="PATCH")
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"token {token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()

def http_post_json(url: str, token: str, payload: dict, headers_extra: dict | None = None, timeout: int = 20):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"token {token}")
    if headers_extra:
        for k, v in headers_extra.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()

def http_post_multipart(url: str, token: str, sudo_user: str, files: dict, timeout: int = 20):
    boundary = f"----WebKitFormBoundary{uuid4().hex}"
    chunks = []
    for field, (fname, content, mime) in files.items():
        if not mime:
            mime = mimetypes.guess_type(fname)[0] or "application/octet-stream"
        chunks.append(
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"{field}\"; filename=\"{fname}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8")
        chunks.append(content)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(chunks)

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    if token:
        req.add_header("Authorization", f"token {token}")
    if sudo_user:
        req.add_header("Sudo", sudo_user)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        resp.read()

# ------------- CREATE (CLI) -------------
def create_user(
    username: str,
    email: str,
    password: str,
    *,
    container: str = "gitea",
    config_path: str = "/data/gitea/conf/app.ini",
    use_puid_pgid: bool = True,
    admin: bool = False,
    must_change_password: bool = False,
) -> int:
    env = load_env_or_die()

    prefix = ["docker", "exec"]
    if use_puid_pgid and env.get("PUID") and env.get("PGID"):
        prefix += ["-u", f"{env['PUID']}:{env['PGID']}"]
    prefix.append(container)

    args = [
        "gitea", "--config", config_path,
        "admin", "user", "create",
        "--username", username,
        "--password", password,
        "--email", email,
        "--must-change-password" if must_change_password else "--must-change-password=false",
    ]
    if admin:
        args.append("--admin")

    cmd = " ".join([shlex.quote(x) for x in prefix + args])
    return run(cmd)

# ------------- EDIT (CLI password + API rename/patch/avatar) -------------
def edit_user(
    username: str,
    *,
    container: str = "gitea",
    config_path: str = "/data/gitea/conf/app.ini",
    use_puid_pgid: bool = True,
    new_username: str = None,
    password: str = None,
    email: str = None,
    full_name: str = None,
    login_name: str = None,
    admin: str = None,
    active: str = None,
    prohibit_login: str = None,
    restricted: str = None,
    visibility: str = None,
    website: str = None,
    location: str = None,
    description: str = None,
    allow_create_organization: str = None,
    allow_git_hook: str = None,
    allow_import_local: str = None,
    max_repo_creation: str = None,
    avatar_path: str = None,
    timeout: int = 20,
) -> dict:
    env = load_env_or_die()
    base_url = (env.get("ROOT_URL") or env.get("GITEA_BASE_URL") or "").rstrip("/")
    token = env.get("GITEA_ADMIN_TOKEN", "")

    # só senha → só CLI
    only_password = (
        password is not None and
        new_username is None and
        email is None and
        full_name is None and
        login_name is None and
        admin is None and
        active is None and
        prohibit_login is None and
        restricted is None and
        visibility is None and
        website is None and
        location is None and
        description is None and
        allow_create_organization is None and
        allow_git_hook is None and
        allow_import_local is None and
        max_repo_creation is None and
        avatar_path is None
    )
    if only_password:
        prefix = ["docker", "exec"]
        if use_puid_pgid and env.get("PUID") and env.get("PGID"):
            prefix += ["-u", f"{env['PUID']}:{env['PGID']}"]
        prefix.append(container)
        args = [
            "gitea", "--config", config_path,
            "admin", "user", "change-password",
            "--username", username,
            "--password", password,
        ]
        cmd = " ".join([shlex.quote(x) for x in prefix + args])
        rc = run(cmd)
        if rc != 0:
            raise RuntimeError(f"Falha ao trocar senha via CLI (exit {rc}).")
        if base_url:
            try:
                user = http_get_json(f"{base_url}/api/v1/users/{urllib.parse.quote(username)}")
                user["username"] = username
                return user
            except Exception:
                pass
        return {"username": username, "password_changed": True}

    # demais casos precisam API admin
    if not base_url:
        raise RuntimeError("ROOT_URL/GITEA_BASE_URL ausente no .env — necessário para rename/patch/avatar.")
    if not token:
        raise RuntimeError("GITEA_ADMIN_TOKEN ausente no .env — necessário para rename/patch/avatar.")

    target = username

    # rename
    if new_username and new_username != username:
        url = f"{base_url}/api/v1/admin/users/{urllib.parse.quote(username)}/rename"
        http_post_json(url, token, {"new_username": new_username}, timeout=timeout)
        target = new_username

    # password (quando há outros campos também)
    if password:
        prefix = ["docker", "exec"]
        if use_puid_pgid and env.get("PUID") and env.get("PGID"):
            prefix += ["-u", f"{env['PUID']}:{env['PGID']}"]
        prefix.append(container)
        args = [
            "gitea", "--config", config_path,
            "admin", "user", "change-password",
            "--username", target,
            "--password", password,
        ]
        cmd = " ".join([shlex.quote(x) for x in prefix + args])
        rc = run(cmd)
        if rc != 0:
            raise RuntimeError(f"Falha ao trocar senha via CLI (exit {rc}).")

    # patch
    payload = {}
    def put_bool(name, value):
        if value is None:
            return
        lv = value.lower()
        if lv not in ("true", "false"):
            raise RuntimeError(f"{name} deve ser 'true' ou 'false'")
        payload[name] = (lv == "true")

    if email is not None: payload["email"] = email
    if full_name is not None: payload["full_name"] = full_name
    if login_name is not None: payload["login_name"] = login_name
    if visibility is not None: payload["visibility"] = visibility
    if website is not None: payload["website"] = website
    if location is not None: payload["location"] = location
    if description is not None: payload["description"] = description
    if max_repo_creation is not None: payload["max_repo_creation"] = int(max_repo_creation)

    put_bool("admin", admin)
    put_bool("active", active)
    put_bool("prohibit_login", prohibit_login)
    put_bool("restricted", restricted)
    put_bool("allow_create_organization", allow_create_organization)
    put_bool("allow_git_hook", allow_git_hook)
    put_bool("allow_import_local", allow_import_local)

    if payload:
        url = f"{base_url}/api/v1/admin/users/{urllib.parse.quote(target)}"
        http_patch_json(url, token, payload, timeout=timeout)

    # avatar
    if avatar_path:
        with open(avatar_path, "rb") as fh:
            content = fh.read()
        url = f"{base_url}/api/v1/user/avatar"
        http_post_multipart(url, token, sudo_user=target,
                            files={"avatar": (os.path.basename(avatar_path), content, None)},
                            timeout=timeout)

    # retorno final
    user = http_get_json(f"{base_url}/api/v1/users/{urllib.parse.quote(target)}")
    user["username"] = target
    return user

# ------------- DELETE (CLI) -------------
def delete_user(
    username: str,
    *,
    container: str = "gitea",
    config_path: str = "/data/gitea/conf/app.ini",
    use_puid_pgid: bool = True,
    purge: bool = True,
) -> int:
    env = load_env_or_die()

    prefix = ["docker", "exec"]
    if use_puid_pgid and env.get("PUID") and env.get("PGID"):
        prefix += ["-u", f"{env['PUID']}:{env['PGID']}"]
    prefix.append(container)

    args = [
        "gitea", "--config", config_path,
        "admin", "user", "delete",
        "--username", username,
    ]
    if purge:
        args.append("--purge")

    cmd = " ".join([shlex.quote(x) for x in prefix + args])
    return run(cmd)

# ------------- SHOW (API pública) -------------
def show_user(username: str, *, timeout: int = 20) -> dict:
    env = load_env_or_die()
    base_url = (env.get("ROOT_URL") or env.get("GITEA_BASE_URL") or "").rstrip("/")
    if not base_url:
        raise RuntimeError("ROOT_URL/GITEA_BASE_URL ausente no .env — necessário para 'show'.")
    return http_get_json(f"{base_url}/api/v1/users/{urllib.parse.quote(username)}", token="", timeout=timeout)

# ------------- CLI -------------
def main():
    parser = argparse.ArgumentParser(description="CLI Gitea (.env no diretório atual): criar, editar, deletar e mostrar usuários")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # create
    pc = sub.add_parser("create", help="Criar usuário via CLI do container")
    pc.add_argument("--container", default="gitea")
    pc.add_argument("--config-path", default="/data/gitea/conf/app.ini")
    pc.add_argument("--no-puid-pgid", action="store_true")
    pc.add_argument("--admin", action="store_true")
    pc.add_argument("--must-change-password", action="store_true")
    pc.add_argument("--username", required=True)
    pc.add_argument("--email", required=True)
    pc.add_argument("--password", required=True)

    # edit
    pe = sub.add_parser("edit", help="Editar qualquer campo do usuário (senha via CLI; resto via API admin)")
    pe.add_argument("--container", default="gitea")
    pe.add_argument("--config-path", default="/data/gitea/conf/app.ini")
    pe.add_argument("--no-puid-pgid", action="store_true")
    pe.add_argument("--username", required=True)
    pe.add_argument("--new-username")
    pe.add_argument("--password")
    pe.add_argument("--email")
    pe.add_argument("--full-name")
    pe.add_argument("--login-name")
    pe.add_argument("--admin")
    pe.add_argument("--active")
    pe.add_argument("--prohibit-login")
    pe.add_argument("--restricted")
    pe.add_argument("--visibility")
    pe.add_argument("--website")
    pe.add_argument("--location")
    pe.add_argument("--description")
    pe.add_argument("--allow-create-organization")
    pe.add_argument("--allow-git-hook")
    pe.add_argument("--allow-import-local")
    pe.add_argument("--max-repo-creation")
    pe.add_argument("--avatar-path")

    # delete
    pd = sub.add_parser("delete", help="Deletar usuário via CLI do container")
    pd.add_argument("--container", default="gitea")
    pd.add_argument("--config-path", default="/data/gitea/conf/app.ini")
    pd.add_argument("--no-puid-pgid", action="store_true")
    pd.add_argument("--no-purge", action="store_true", help="não usar --purge")
    pd.add_argument("--username", required=True)

    # show
    ps = sub.add_parser("show", help="Mostrar usuário (API pública)")
    ps.add_argument("--username", required=True)

    args = parser.parse_args()

    try:
        if args.cmd == "create":
            rc = create_user(
                username=args.username,
                email=args.email,
                password=args.password,
                container=args.container,
                config_path=args.config_path,
                use_puid_pgid=not args.no_puid_pgid,
                admin=args.admin,
                must_change_password=args.must_change_password,
            )
            if rc == 0:
                print("✅ Usuário criado com sucesso.")
                sys.exit(0)
            print(f"❌ Falha ao criar usuário (exit code {rc}).", file=sys.stderr)
            sys.exit(rc)

        elif args.cmd == "edit":
            result = edit_user(
                username=args.username,
                container=args.container,
                config_path=args.config_path,
                use_puid_pgid=not args.no_puid_pgid,
                new_username=args.new_username,
                password=args.password,
                email=args.email,
                full_name=args.full_name,
                login_name=args.login_name,
                admin=args.admin,
                active=args.active,
                prohibit_login=args.prohibit_login,
                restricted=args.restricted,
                visibility=args.visibility,
                website=args.website,
                location=args.location,
                description=args.description,
                allow_create_organization=args.allow_create_organization,
                allow_git_hook=args.allow_git_hook,
                allow_import_local=args.allow_import_local,
                max_repo_creation=args.max_repo_creation,
                avatar_path=args.avatar_path,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            sys.exit(0)

        elif args.cmd == "delete":
            rc = delete_user(
                username=args.username,
                container=args.container,
                config_path=args.config_path,
                use_puid_pgid=not args.no_puid_pgid,
                purge=not args.no_purge,
            )
            if rc == 0:
                print("✅ Usuário deletado com sucesso.")
                sys.exit(0)
            print(f"❌ Falha ao deletar usuário (exit code {rc}).", file=sys.stderr)
            sys.exit(rc)

        elif args.cmd == "show":
            info = show_user(username=args.username)
            print(json.dumps(info, ensure_ascii=False, indent=2))
            sys.exit(0)

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"❌ HTTP {e.code} {e.reason} — {body}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"❌ Erro: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
