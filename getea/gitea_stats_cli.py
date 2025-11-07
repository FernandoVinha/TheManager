#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
gitea_stats_cli.py
Conta linhas adicionadas/removidas por usuário em um repositório do Gitea.

Lê SEMPRE o .env (ROOT_URL/GITEA_BASE_URL e GITEA_ADMIN_TOKEN) do diretório atual.

Uso:
  # estatísticas por autor (branch main, últimos 30 dias)
  python gitea_stats_cli.py lines --owner john --repo demo --branch main --since 2025-10-01 --until 2025-11-05

Opções:
  --owner / --repo     (obrigatório)
  --branch             (padrão: default do repo; se informar, filtra)
  --since / --until    (ISO yyyy-mm-dd; filtra por data do commit)
  --max-pages          (padrão 50; cada página 50 commits)
  --raw                (imprime JSON bruto agregado)
"""

import argparse
import os
import sys
import json
import urllib.request, urllib.parse, urllib.error
from datetime import datetime

ENV_FILENAME = ".env"

def load_env_or_die() -> dict:
    path = os.path.join(os.getcwd(), ENV_FILENAME)
    if not os.path.isfile(path):
        raise RuntimeError(f"Arquivo {ENV_FILENAME} não encontrado em {os.getcwd()}")
    env = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env

def base_url_and_token():
    env = load_env_or_die()
    base = (env.get("ROOT_URL") or env.get("GITEA_BASE_URL") or "").rstrip("/")
    tok = env.get("GITEA_ADMIN_TOKEN", "")
    if not base:
        raise RuntimeError("Defina ROOT_URL ou GITEA_BASE_URL no .env")
    if not tok:
        raise RuntimeError("Defina GITEA_ADMIN_TOKEN no .env")
    return base, tok

def http(method: str, url: str, token: str, params: dict | None = None, timeout: int = 25):
    if params:
        q = urllib.parse.urlencode(params, doseq=True)
        url = f"{url}?{q}"
    req = urllib.request.Request(url, method=method, headers={
        "Accept": "application/json",
        "Authorization": f"token {token}",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace") or ""
        if body and resp.headers.get("Content-Type","").startswith("application/json"):
            return json.loads(body)
        return body

def parse_iso_date(s: str | None):
    if not s: return None
    return datetime.fromisoformat(s)

def author_key(commit_obj: dict) -> tuple[str,str]:
    """
    Retorna (username_ou_nome, email_ou_vazio) usando a melhor fonte disponível.
    Prioriza author.login/username -> depois commit.author.name/email -> depois committer.
    """
    # prefer author (conta do Gitea)
    a = commit_obj.get("author") or {}
    if a.get("login") or a.get("username"):
        return (a.get("login") or a.get("username"), a.get("email") or "")
    # dados do commit (nome/email)
    c = (commit_obj.get("commit") or {}).get("author") or {}
    if c.get("name") or c.get("email"):
        return (c.get("name") or "desconhecido", c.get("email") or "")
    # fallback: committer
    cm = (commit_obj.get("commit") or {}).get("committer") or {}
    if cm.get("name") or cm.get("email"):
        return (cm.get("name") or "desconhecido", cm.get("email") or "")
    return ("desconhecido", "")

def in_date_range(commit_obj: dict, since_dt, until_dt) -> bool:
    date_str = ((commit_obj.get("commit") or {}).get("author") or {}).get("date")
    if not date_str:
        return True
    try:
        # formatos ISO do Gitea costumam incluir timezone (ex: 2025-11-05T12:34:56Z)
        dt = datetime.fromisoformat(date_str.replace("Z","+00:00"))
    except Exception:
        return True
    if since_dt and dt < since_dt: return False
    if until_dt and dt > until_dt: return False
    return True

def fetch_commits_paginated(base, token, owner, repo, branch=None, since=None, until=None, max_pages=50, per_page=50):
    """
    Busca commits paginados; para cada commit, busca detalhes (stats) e rende o objeto detalhado.
    """
    results = []
    page = 1
    params_base = {"limit": per_page, "page": page}
    if branch: params_base["sha"] = branch  # filtro por branch
    # filtros since/until (API de commits nem sempre filtra por data; então filtramos manualmente também)
    # alguns Gitea aceitam since/until em /commits; manter tentativa:
    if since: params_base["since"] = since
    if until: params_base["until"] = until

    while page <= max_pages:
        params = dict(params_base)
        params["page"] = page
        lst = http("GET", f"{base}/api/v1/repos/{owner}/{repo}/commits", token, params=params)
        if not lst:
            break
        for item in lst:
            sha = item.get("sha") or item.get("id")
            if not sha:
                continue
            # data-range filter (manual)
            if not in_date_range(item, parse_iso_date(since), parse_iso_date(until)):
                continue
            # details with stats
            detail = http("GET", f"{base}/api/v1/repos/{owner}/{repo}/commits/{sha}", token)
            # injeta autor resolvido + stats
            user_key = author_key(detail)
            stats = (detail.get("stats") or {})
            results.append({
                "sha": sha,
                "author": user_key[0],
                "email": user_key[1],
                "date": ((detail.get("commit") or {}).get("author") or {}).get("date"),
                "additions": stats.get("additions", 0),
                "deletions": stats.get("deletions", 0),
                "total": stats.get("total", 0),
            })
        page += 1
    return results

def aggregate_by_author(rows: list[dict]) -> list[dict]:
    agg = {}
    for r in rows:
        k = (r["author"] or "desconhecido", r["email"] or "")
        if k not in agg:
            agg[k] = {"author": k[0], "email": k[1], "commits": 0, "additions": 0, "deletions": 0}
        agg[k]["commits"] += 1
        agg[k]["additions"] += int(r.get("additions", 0) or 0)
        agg[k]["deletions"] += int(r.get("deletions", 0) or 0)
    # ordena por additions - deletions (net) desc
    out = list(agg.values())
    out.sort(key=lambda x: (x["additions"] - x["deletions"], x["additions"]), reverse=True)
    return out

def print_table(rows: list[dict]):
    if not rows:
        print("Nenhum resultado.")
        return
    # colunas: autor, email, commits, +, -, net
    print(f"{'AUTHOR':20} {'EMAIL':28} {'COMMITS':7} {'+ADD':7} {'-DEL':7} {'NET':7}")
    print("-"*80)
    for r in rows:
        net = r["additions"] - r["deletions"]
        print(f"{(r['author'] or '')[:20]:20} {(r['email'] or '')[:28]:28} {r['commits']:7d} {r['additions']:7d} {r['deletions']:7d} {net:7d}")

def cmd_lines(owner, repo, branch=None, since=None, until=None, max_pages=50, raw=False):
    base, token = base_url_and_token()
    rows = fetch_commits_paginated(base, token, owner, repo, branch=branch, since=since, until=until, max_pages=max_pages)
    agg = aggregate_by_author(rows)
    if raw:
        print(json.dumps({"by_author": agg, "commits": rows}, ensure_ascii=False, indent=2))
    else:
        print_table(agg)

def main():
    ap = argparse.ArgumentParser(description="Gitea Stats CLI (.env no diretório atual)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ls = sub.add_parser("lines", help="Somar linhas adicionadas/removidas por autor")
    ls.add_argument("--owner", required=True)
    ls.add_argument("--repo", required=True)
    ls.add_argument("--branch")
    ls.add_argument("--since", help="YYYY-MM-DD")
    ls.add_argument("--until", help="YYYY-MM-DD")
    ls.add_argument("--max-pages", type=int, default=50)
    ls.add_argument("--raw", action="store_true", help="imprime JSON agregado e commits")

    args = ap.parse_args()
    try:
        if args.cmd == "lines":
            cmd_lines(args.owner, args.repo, branch=args.branch, since=args.since, until=args.until, max_pages=args.max_pages, raw=args.raw)
        else:
            raise RuntimeError("comando inválido")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"❌ HTTP {e.code} {e.reason} — {body}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"❌ Erro: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
