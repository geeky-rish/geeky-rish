#!/usr/bin/env python3
"""Refresh the dynamic sections of the profile README.

Fills the blocks between
    <!-- ACTIVITY:START --> ... <!-- ACTIVITY:END -->
    <!-- REPOS:START -->    ... <!-- REPOS:END -->
using the public GitHub API. Stdlib only, no third-party services.
If an API call fails, the existing block is left untouched.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime

USER = os.environ.get("USERNAME") or "geeky-rish"
TOKEN = os.environ.get("GITHUB_TOKEN")
README = os.environ.get("README_PATH", "README.md")
API = "https://api.github.com"


def get(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USER}-profile-readme",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(API + path, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def fmt_date(iso):
    d = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
    return f"{d.day} {d:%b %Y}"


def clean(text, limit=90):
    text = (text or "").replace("|", "\\|").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


# ---------- recent repos ----------
def repos_block():
    repos = get(f"/users/{USER}/repos?type=owner&sort=pushed&per_page=100")
    keep = [
        r for r in repos
        if not r["fork"] and not r["archived"] and r["name"].lower() != USER.lower()
    ][:6]
    if not keep:
        return "_Nothing public yet._"
    rows = [
        "| Repo | What it is | Language | ⭐ | Last push |",
        "|---|---|---|---|---|",
    ]
    for r in keep:
        rows.append(
            f"| [**{r['name']}**]({r['html_url']}) | {clean(r['description'])} "
            f"| {r['language'] or '—'} | {r['stargazers_count']} | {fmt_date(r['pushed_at'])} |"
        )
    return "\n".join(rows)


# ---------- recent activity ----------
def describe(e):
    t, repo, p = e["type"], e["repo"]["name"], e.get("payload", {})
    link = f"[{repo.split('/')[-1]}](https://github.com/{repo})"
    if t == "PushEvent":
        branch = p.get("ref", "").replace("refs/heads/", "")
        return "⬆️", f"Pushed to {link}" + (f" (`{branch}`)" if branch else "")
    if t == "PullRequestEvent":
        pr = p.get("pull_request", {})
        act = "Merged" if pr.get("merged") else (p.get("action") or "updated").capitalize()
        num = pr.get("number")
        ref = f"[#{num}]({pr['html_url']})" if num and pr.get("html_url") else f"#{num}" if num else "a PR"
        return "🔀", f"{act} PR {ref} in {link}"
    if t == "IssuesEvent":
        iss = p.get("issue", {})
        num = iss.get("number")
        ref = f"[#{num}]({iss['html_url']})" if num and iss.get("html_url") else "an issue"
        return "🐛", f"{(p.get('action') or 'updated').capitalize()} issue {ref} in {link}"
    if t == "ReleaseEvent":
        tag = p.get("release", {}).get("tag_name", "")
        return "🚀", f"Released {('`' + tag + '` ') if tag else ''}in {link}"
    if t == "CreateEvent" and p.get("ref_type") == "repository":
        return "🆕", f"Created {link}"
    if t == "ForkEvent":
        return "🍴", f"Forked {link}"
    return None


def activity_block():
    events = get(f"/users/{USER}/events/public?per_page=50")
    lines, seen = [], set()
    for e in events:
        d = describe(e)
        if not d:
            continue
        icon, text = d
        if text in seen:
            continue
        seen.add(text)
        lines.append(f"- {icon} {text} · <sub>{fmt_date(e['created_at'])}</sub>")
        if len(lines) == 5:
            break
    return "\n".join(lines) if lines else "_No public activity in the last 90 days._"


def replace_block(text, tag, body):
    pat = re.compile(rf"(<!-- {tag}:START -->)(.*?)(<!-- {tag}:END -->)", re.S)
    if not pat.search(text):
        print(f"[skip] marker {tag} not found in {README}")
        return text
    return pat.sub(lambda m: f"{m.group(1)}\n{body}\n{m.group(3)}", text)


def main():
    with open(README, encoding="utf-8") as f:
        original = f.read()
    text = original
    for tag, fn in (("ACTIVITY", activity_block), ("REPOS", repos_block)):
        try:
            text = replace_block(text, tag, fn())
            print(f"[ok]   {tag}")
        except Exception as exc:  # keep old content on any failure
            print(f"[warn] {tag} not refreshed: {exc}")
    if text != original:
        with open(README, "w", encoding="utf-8") as f:
            f.write(text)
        print("README updated")
    else:
        print("No changes")


if __name__ == "__main__":
    sys.exit(main())
