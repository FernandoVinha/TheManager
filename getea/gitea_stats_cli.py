import argparse
import os
import sys
import json
import urllib.request, urllib.parse, urllib.error
from datetime import datetime

ENV_FILENAME = ".env"


def load_env_or_die() -> dict:
    """
    Loads .env from current working directory.
    Raises if not found.
    """
    path = os.path.join(os.getcwd(), ENV_FILENAME)
    if not os.path.isfile(path):
        raise RuntimeError(f"{ENV_FILENAME} file not found in {os.getcwd()}")
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
    """
    Extracts ROOT_URL or GITEA_BASE_URL + GITEA_ADMIN_TOKEN from .env.
    """
    env = load_env_or_die()
    base = (env.get("ROOT_URL") or env.get("GITEA_BASE_URL") or "").rstrip("/")
    tok = env.get("GITEA_ADMIN_TOKEN", "")
    if not base:
        raise RuntimeError("Define ROOT_URL or GITEA_BASE_URL in .env")
    if not tok:
        raise RuntimeError("Define GITEA_ADMIN_TOKEN in .env")
    return base, tok


def http(method: str, url: str, token: str, params: dict | None = None, timeout: int = 25):
    """
    Simple HTTP wrapper returning JSON when Content-Type is JSON.
    """
    if params:
        q = urllib.parse.urlencode(params, doseq=True)
        url = f"{url}?{q}"

    req = urllib.request.Request(
        url,
        method=method,
        headers={
            "Accept": "application/json",
            "Authorization": f"token {token}",
        },
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace") or ""
        if body and resp.headers.get("Content-Type", "").startswith("application/json"):
            return json.loads(body)
        return body


def parse_iso_date(s: str | None):
    if not s:
        return None
    return datetime.fromisoformat(s)


def author_key(commit_obj: dict) -> tuple[str, str]:
    """
    Returns (username_or_name, email_or_blank) from the best available location.
    Priority: author.login/username → commit.author → committer → fallback.
    """
    # prefer Gitea account
    a = commit_obj.get("author") or {}
    if a.get("login") or a.get("username"):
        return (a.get("login") or a.get("username"), a.get("email") or "")

    # raw commit data
    c = (commit_obj.get("commit") or {}).get("author") or {}
    if c.get("name") or c.get("email"):
        return (c.get("name") or "unknown", c.get("email") or "")

    # fallback: committer
    cm = (commit_obj.get("commit") or {}).get("committer") or {}
    if cm.get("name") or cm.get("email"):
        return (cm.get("name") or "unknown", cm.get("email") or "")

    return ("unknown", "")


def in_date_range(commit_obj: dict, since_dt, until_dt) -> bool:
    """
    Returns True if commit is within date filter.
    """
    date_str = ((commit_obj.get("commit") or {}).get("author") or {}).get("date")
    if not date_str:
        return True
    try:
        # Gitea usually provides ISO with timezone
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return True

    if since_dt and dt < since_dt:
        return False
    if until_dt and dt > until_dt:
        return False
    return True


def fetch_commits_paginated(
    base,
    token,
    owner,
    repo,
    branch=None,
    since=None,
    until=None,
    max_pages=50,
    per_page=50,
):
    """
    Fetch commits paginated; for each commit, fetch detail (stats).
    Returns a list of commit dicts.
    """
    results = []
    page = 1
    params_base = {"limit": per_page, "page": page}

    if branch:
        params_base["sha"] = branch  # filter by branch

    # try passing since/until to API; also manually filter
    if since:
        params_base["since"] = since
    if until:
        params_base["until"] = until

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

            # manual date filter
            if not in_date_range(item, parse_iso_date(since), parse_iso_date(until)):
                continue

            # detailed view
            detail = http("GET", f"{base}/api/v1/repos/{owner}/{repo}/commits/{sha}", token)
            user_key = author_key(detail)
            stats = (detail.get("stats") or {})

            results.append(
                {
                    "sha": sha,
                    "author": user_key[0],
                    "email": user_key[1],
                    "date": ((detail.get("commit") or {}).get("author") or {}).get("date"),
                    "additions": stats.get("additions", 0),
                    "deletions": stats.get("deletions", 0),
                    "total": stats.get("total", 0),
                }
            )

        page += 1

    return results


def aggregate_by_author(rows: list[dict]) -> list[dict]:
    """
    Aggregates commit stats by author.
    """
    agg = {}
    for r in rows:
        k = (r["author"] or "unknown", r["email"] or "")
        if k not in agg:
            agg[k] = {
                "author": k[0],
                "email": k[1],
                "commits": 0,
                "additions": 0,
                "deletions": 0,
            }
        agg[k]["commits"] += 1
        agg[k]["additions"] += int(r.get("additions", 0) or 0)
        agg[k]["deletions"] += int(r.get("deletions", 0) or 0)

    out = list(agg.values())
    # Sort by net lines desc, then additions desc
    out.sort(key=lambda x: (x["additions"] - x["deletions"], x["additions"]), reverse=True)
    return out


def print_table(rows: list[dict]):
    """
    Pretty-print table.
    """
    if not rows:
        print("No results.")
        return

    print(f"{'AUTHOR':20} {'EMAIL':28} {'COMMITS':7} {'+ADD':7} {'-DEL':7} {'NET':7}")
    print("-" * 80)

    for r in rows:
        net = r["additions"] - r["deletions"]
        print(
            f"{(r['author'] or '')[:20]:20} "
            f"{(r['email'] or '')[:28]:28} "
            f"{r['commits']:7d} "
            f"{r['additions']:7d} "
            f"{r['deletions']:7d} "
            f"{net:7d}"
        )


def cmd_lines(owner, repo, branch=None, since=None, until=None, max_pages=50, raw=False):
    """
    Command: summarize per-author statistics.
    """
    base, token = base_url_and_token()
    rows = fetch_commits_paginated(
        base,
        token,
        owner,
        repo,
        branch=branch,
        since=since,
        until=until,
        max_pages=max_pages,
    )
    agg = aggregate_by_author(rows)
    if raw:
        print(json.dumps({"by_author": agg, "commits": rows}, ensure_ascii=False, indent=2))
    else:
        print_table(agg)


def main():
    ap = argparse.ArgumentParser(description="Gitea Stats CLI (.env in current directory)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ls = sub.add_parser("lines", help="Sum added/removed lines grouped by author")
    ls.add_argument("--owner", required=True)
    ls.add_argument("--repo", required=True)
    ls.add_argument("--branch")
    ls.add_argument("--since", help="YYYY-MM-DD")
    ls.add_argument("--until", help="YYYY-MM-DD")
    ls.add_argument("--max-pages", type=int, default=50)
    ls.add_argument("--raw", action="store_true", help="prints aggregated + raw JSON")

    args = ap.parse_args()

    try:
        if args.cmd == "lines":
            cmd_lines(
                args.owner,
                args.repo,
                branch=args.branch,
                since=args.since,
                until=args.until,
                max_pages=args.max_pages,
                raw=args.raw,
            )
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
