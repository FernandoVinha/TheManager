#getea/gitea_user_cli.py

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

ENV_FILENAME = ".env"
DEFAULT_CONTAINER = os.environ.get("GITEA_CONTAINER", "gitea")
DEFAULT_CONFIG_PATH = "/data/gitea/conf/app.ini"
DEFAULT_TIMEOUT = 20

# ------------------------------ .env loader ------------------------------

def load_env_or_die() -> Dict[str, str]:
    path = os.path.join(os.getcwd(), ENV_FILENAME)
    if not os.path.isfile(path):
        raise RuntimeError(f"Missing {ENV_FILENAME} in current directory: {os.getcwd()}")
    env: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip().rstrip("\r")
            if not line or line.startswith("#") or "=" not in line:
                continue
            # allow: export KEY=VALUE
            if line.startswith("export "):
                line = line[len("export "):]
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                v = v[1:-1]
            env[k] = v
    return env

# ------------------------------ process helpers ------------------------------

def run_argv(argv: List[str], *, verbose: bool = False, dry_run: bool = False) -> Tuple[int, str, str]:
    if verbose or dry_run:
        print("$", " ".join(map(shlex_quote, argv)))
    if dry_run:
        return 0, "", ""
    proc = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def shlex_quote(s: str) -> str:
    # minimal portable quoting for echoing commands (not for execution)
    if re.fullmatch(r"[A-Za-z0-9@%_+=:,./-]+", s):
        return s
    return "'" + s.replace("'", "'\\''") + "'"


def docker_exec_argv(container: str, puid: Optional[str], pgid: Optional[str], inner: List[str]) -> List[str]:
    argv = ["docker", "exec"]
    if puid and pgid:
        argv += ["-u", f"{puid}:{pgid}"]
    argv.append(container)
    argv += inner
    return argv


def ensure_docker_container(env: Dict[str, str], container: str, *, verbose: bool = False) -> None:
    code, out, err = run_argv(["docker", "ps", "--format", "{{.Names}}"], verbose=verbose)
    if code != 0:
        raise RuntimeError(f"Cannot talk to docker daemon (docker ps). {err.strip()}")
    names = {n.strip() for n in out.splitlines() if n.strip()}
    if container not in names:
        raise RuntimeError(f"Container '{container}' is not running. Running containers: {', '.join(sorted(names)) or 'none'}")

# ------------------------------ HTTP helpers ------------------------------

def http_get_json(url: str, token: str = "", timeout: int = DEFAULT_TIMEOUT) -> dict:
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", f"token {token}")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read().decode("utf-8", errors="replace")
        return json.loads(data) if data else {}


def http_patch_json(url: str, token: str, payload: dict, timeout: int = DEFAULT_TIMEOUT) -> None:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="PATCH")
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"token {token}")
    with urllib.request.urlopen(req, timeout=timeout):
        pass


def http_post_json(url: str, token: str, payload: dict, headers_extra: Optional[dict] = None, timeout: int = DEFAULT_TIMEOUT) -> None:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Accept", "application/json")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"token {token}")
    if headers_extra:
        for k, v in headers_extra.items():
            req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout):
        pass


def http_post_multipart(url: str, token: str, sudo_user: str, files: dict, timeout: int = DEFAULT_TIMEOUT) -> None:
    boundary = f"----WebKitFormBoundary{uuid4().hex}"
    chunks: List[bytes] = []
    for field, (fname, content, mime) in files.items():
        if not mime:
            mime = mimetypes.guess_type(fname)[0] or "application/octet-stream"
        chunks.append(
            (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"{field}\"; filename=\"{fname}\"\r\n"
                f"Content-Type: {mime}\r\n\r\n"
            ).encode("utf-8")
        )
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
    with urllib.request.urlopen(req, timeout=timeout):
        pass

# ------------------------------ core ops ------------------------------

def create_user(
    username: str,
    email: str,
    password: str,
    *,
    container: str = DEFAULT_CONTAINER,
    config_path: str = DEFAULT_CONFIG_PATH,
    use_puid_pgid: bool = True,
    admin: bool = False,
    must_change_password: bool = False,
    verbose: bool = False,
    dry_run: bool = False,
) -> Tuple[int, str]:
    env = load_env_or_die()
    ensure_docker_container(env, container, verbose=verbose)

    inner = [
        "gitea", "--config", config_path,
        "admin", "user", "create",
        "--username", username,
        "--password", password,
        "--email", email,
        "--must-change-password" if must_change_password else "--must-change-password=false",
    ]
    if admin:
        inner.append("--admin")

    argv = docker_exec_argv(container, env.get("PUID"), env.get("PGID") if use_puid_pgid else None, inner)
    rc, out, err = run_argv(argv, verbose=verbose, dry_run=dry_run)
    msg = out.strip() or err.strip()
    return rc, msg


def change_password(
    username: str,
    password: str,
    *,
    container: str,
    config_path: str,
    use_puid_pgid: bool,
    verbose: bool = False,
    dry_run: bool = False,
) -> None:
    env = load_env_or_die()
    ensure_docker_container(env, container, verbose=verbose)
    inner = [
        "gitea", "--config", config_path,
        "admin", "user", "change-password",
        "--username", username,
        "--password", password,
    ]
    argv = docker_exec_argv(container, env.get("PUID") if use_puid_pgid else None, env.get("PGID") if use_puid_pgid else None, inner)
    rc, out, err = run_argv(argv, verbose=verbose, dry_run=dry_run)
    if rc != 0:
        raise RuntimeError(f"Failed to change password (exit {rc}): {err.strip() or out.strip()}")


def edit_user(
    username: str,
    *,
    container: str = DEFAULT_CONTAINER,
    config_path: str = DEFAULT_CONFIG_PATH,
    use_puid_pgid: bool = True,
    new_username: Optional[str] = None,
    password: Optional[str] = None,
    email: Optional[str] = None,
    full_name: Optional[str] = None,
    login_name: Optional[str] = None,
    admin: Optional[str] = None,
    active: Optional[str] = None,
    prohibit_login: Optional[str] = None,
    restricted: Optional[str] = None,
    visibility: Optional[str] = None,
    website: Optional[str] = None,
    location: Optional[str] = None,
    description: Optional[str] = None,
    allow_create_organization: Optional[str] = None,
    allow_git_hook: Optional[str] = None,
    allow_import_local: Optional[str] = None,
    max_repo_creation: Optional[str] = None,
    avatar_path: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
    verbose: bool = False,
    dry_run: bool = False,
) -> dict:
    env = load_env_or_die()
    base_url = (env.get("ROOT_URL") or env.get("GITEA_BASE_URL") or "").rstrip("/")
    token = env.get("GITEA_ADMIN_TOKEN", "")

    # password-only path: CLI only
    if (
        password is not None and
        all(v is None for v in [new_username, email, full_name, login_name, admin, active, prohibit_login,
                                restricted, visibility, website, location, description,
                                allow_create_organization, allow_git_hook, allow_import_local,
                                max_repo_creation, avatar_path])
    ):
        change_password(username, password, container=container, config_path=config_path,
                        use_puid_pgid=use_puid_pgid, verbose=verbose, dry_run=dry_run)
        if base_url:
            try:
                user = http_get_json(f"{base_url}/api/v1/users/{urllib.parse.quote(username)}")
                user["username"] = username
                return user
            except Exception:
                return {"username": username, "password_changed": True}
        return {"username": username, "password_changed": True}

    if not base_url:
        raise RuntimeError("ROOT_URL or GITEA_BASE_URL is required for rename/patch/avatar operations.")
    if not token:
        raise RuntimeError("GITEA_ADMIN_TOKEN is required for rename/patch/avatar operations.")

    target = username

    # rename
    if new_username and new_username != username:
        http_post_json(f"{base_url}/api/v1/admin/users/{urllib.parse.quote(username)}/rename",
                       token, {"new_username": new_username}, timeout=timeout)
        target = new_username

    # if password provided alongside other fields → still via CLI
    if password:
        change_password(target, password, container=container, config_path=config_path,
                        use_puid_pgid=use_puid_pgid, verbose=verbose, dry_run=dry_run)

    # patch
    payload: Dict[str, object] = {}

    def put_bool(name: str, value: Optional[str]) -> None:
        if value is None:
            return
        lv = value.lower()
        if lv not in ("true", "false"):
            raise RuntimeError(f"{name} must be 'true' or 'false'")
        payload[name] = (lv == "true")

    if email is not None:
        payload["email"] = email
    if full_name is not None:
        payload["full_name"] = full_name
    if login_name is not None:
        payload["login_name"] = login_name
    if visibility is not None:
        payload["visibility"] = visibility
    if website is not None:
        payload["website"] = website
    if location is not None:
        payload["location"] = location
    if description is not None:
        payload["description"] = description
    if max_repo_creation is not None:
        payload["max_repo_creation"] = int(max_repo_creation)

    put_bool("admin", admin)
    put_bool("active", active)
    put_bool("prohibit_login", prohibit_login)
    put_bool("restricted", restricted)
    put_bool("allow_create_organization", allow_create_organization)
    put_bool("allow_git_hook", allow_git_hook)
    put_bool("allow_import_local", allow_import_local)

    if payload:
        http_patch_json(f"{base_url}/api/v1/admin/users/{urllib.parse.quote(target)}", token, payload, timeout=timeout)

    if avatar_path:
        with open(avatar_path, "rb") as fh:
            content = fh.read()
        http_post_multipart(
            f"{base_url}/api/v1/user/avatar", token, sudo_user=target,
            files={"avatar": (os.path.basename(avatar_path), content, None)}, timeout=timeout
        )

    user = http_get_json(f"{base_url}/api/v1/users/{urllib.parse.quote(target)}")
    user["username"] = target
    return user


def delete_user(
    username: str,
    *,
    container: str = DEFAULT_CONTAINER,
    config_path: str = DEFAULT_CONFIG_PATH,
    use_puid_pgid: bool = True,
    purge: bool = True,
    verbose: bool = False,
    dry_run: bool = False,
) -> Tuple[int, str]:
    env = load_env_or_die()
    ensure_docker_container(env, container, verbose=verbose)
    inner = [
        "gitea", "--config", config_path,
        "admin", "user", "delete",
        "--username", username,
    ]
    if purge:
        inner.append("--purge")
    argv = docker_exec_argv(container, env.get("PUID") if use_puid_pgid else None, env.get("PGID") if use_puid_pgid else None, inner)
    rc, out, err = run_argv(argv, verbose=verbose, dry_run=dry_run)
    msg = out.strip() or err.strip()
    return rc, msg


def show_user(username: str, *, timeout: int = DEFAULT_TIMEOUT) -> dict:
    env = load_env_or_die()
    base_url = (env.get("ROOT_URL") or env.get("GITEA_BASE_URL") or "").rstrip("/")
    if not base_url:
        raise RuntimeError("ROOT_URL or GITEA_BASE_URL is required for 'show'.")
    return http_get_json(f"{base_url}/api/v1/users/{urllib.parse.quote(username)}", token="", timeout=timeout)

# ------------------------------ CLI ------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Gitea user CLI (reads .env from current directory)")
    p.add_argument("--verbose", action="store_true", help="echo commands and extra info")
    p.add_argument("--dry-run", action="store_true", help="don't execute mutations, just print")
    p.add_argument("--json", action="store_true", help="force JSON output for create/delete")

    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("create", help="Create user via container CLI")
    pc.add_argument("--container", default=DEFAULT_CONTAINER)
    pc.add_argument("--config-path", default=DEFAULT_CONFIG_PATH)
    pc.add_argument("--no-puid-pgid", action="store_true")
    pc.add_argument("--admin", action="store_true")
    pc.add_argument("--must-change-password", action="store_true")
    pc.add_argument("--username", required=True)
    pc.add_argument("--email", required=True)
    pc.add_argument("--password", required=True)

    pe = sub.add_parser("edit", help="Edit any user field (password via CLI; others via Admin API)")
    pe.add_argument("--container", default=DEFAULT_CONTAINER)
    pe.add_argument("--config-path", default=DEFAULT_CONFIG_PATH)
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

    pd = sub.add_parser("delete", help="Delete user via container CLI")
    pd.add_argument("--container", default=DEFAULT_CONTAINER)
    pd.add_argument("--config-path", default=DEFAULT_CONFIG_PATH)
    pd.add_argument("--no-puid-pgid", action="store_true")
    pd.add_argument("--no-purge", action="store_true", help="do not pass --purge to gitea")
    pd.add_argument("--username", required=True)

    ps = sub.add_parser("show", help="Show user (public API)")
    ps.add_argument("--username", required=True)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.cmd == "create":
            rc, msg = create_user(
                username=args.username,
                email=args.email,
                password=args.password,
                container=args.container,
                config_path=args.config_path,
                use_puid_pgid=not args.no_puid_pgid,
                admin=args.admin,
                must_change_password=args.must_change_password,
                verbose=args.verbose,
                dry_run=args.dry_run,
            )
            if args.json:
                out = {"op": "create", "username": args.username, "exit_code": rc, "message": msg}
                print(json.dumps(out, ensure_ascii=False))
            else:
                print("User created successfully." if rc == 0 else f"Failed to create user (exit {rc}). {msg}")
            sys.exit(0 if rc == 0 else 2)

        if args.cmd == "edit":
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
                verbose=args.verbose,
                dry_run=args.dry_run,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            sys.exit(0)

        if args.cmd == "delete":
            rc, msg = delete_user(
                username=args.username,
                container=args.container,
                config_path=args.config_path,
                use_puid_pgid=not args.no_puid_pgid,
                purge=not args.no_purge,
                verbose=args.verbose,
                dry_run=args.dry_run,
            )
            if args.json:
                out = {"op": "delete", "username": args.username, "exit_code": rc, "message": msg}
                print(json.dumps(out, ensure_ascii=False))
            else:
                print("User deleted successfully." if rc == 0 else f"Failed to delete user (exit {rc}). {msg}")
            sys.exit(0 if rc == 0 else 2)

        if args.cmd == "show":
            info = show_user(username=args.username)
            print(json.dumps(info, ensure_ascii=False, indent=2))
            sys.exit(0)

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code} {e.reason} — {body}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
