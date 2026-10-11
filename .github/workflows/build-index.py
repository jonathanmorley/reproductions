#!/usr/bin/env python3
"""Regenerate the README index table from repro branches: a branch
counts iff it carries an executable root repro.sh (doc = root
README.md), or — legacy — a REPRO.md exactly one level down.
Branch names with slashes work unescaped in github.com tree URLs.
Automation (ci/*, renovate/*, github/*) is exempt and skipped.

Usage: build-index.py [--write] [--repo OWNER/REPO] [--readme PATH]
Without --write, prints the table to stdout. With --write, splices
it between the REPRO-INDEX markers (fails loudly if absent) and
prints changed/unchanged.
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

MARK_START = "<!-- REPRO-INDEX:START -->"
MARK_END = "<!-- REPRO-INDEX:END -->"


def api(repo, token, path):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}{path}",
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--readme", default="README.md")
    a = ap.parse_args()
    token = os.environ.get("GH_TOKEN", "")
    if not a.repo or not token:
        sys.exit("need --repo (or GITHUB_REPOSITORY) and GH_TOKEN")

    branches = []
    page = 1
    while True:
        batch = api(a.repo, token, f"/branches?per_page=100&page={page}")
        if not batch:
            break
        branches += [b["name"] for b in batch]
        page += 1

    rows = []
    for br in sorted(branches):
        if br == "main" or br.startswith(("ci/", "renovate/", "github/")):
            continue
        # Trees API: the contents API omits modes, and the exec bit
        # is the contract signal. Recursive listing covers the legacy
        # one-level layout in the same call.
        head = api(a.repo, token, "/branches/" + urllib.parse.quote(br, safe=""))
        tree = api(a.repo, token, "/git/trees/" + head["commit"]["sha"] + "?recursive=1")
        paths = {(e.get("path"), e.get("mode")) for e in tree.get("tree", [])}
        loc = None
        if any(p == "repro.sh" and m == "100755" for p, m in paths):
            loc = "README.md"
        else:
            cands = sorted({p.split("/")[0] for p, m in paths
                            if "/" in p and p.endswith("/REPRO.md")
                            and p.count("/") == 1})
            if cands:
                loc = cands[0] + "/REPRO.md"
        if not loc:
            continue
        doc = next((e["sha"] for e in tree["tree"] if e.get("path") == loc), None)
        if not doc:
            continue
        blob = api(a.repo, token, "/git/blobs/" + doc)
        raw = base64.b64decode(blob["content"])
        title = "(untitled)"
        for line in raw.decode("utf-8", "replace").splitlines():
            if line.startswith("# "):
                title = line[2:].strip().replace("|", "\\|")
                break
        rows.append((br, loc, title))

    table = ["| Branch | Entry | What |", "|---|---|---|"]
    for br, loc, title in rows:
        table.append(
            f"| `{br}` "
            f"| [{loc}](https://github.com/{a.repo}/blob/{br}/{loc}) "
            f"| {title} |"
        )
    body = "\n".join(table) + "\n"
    if not a.write:
        sys.stdout.write(body)
        return
    with open(a.readme) as f:
        text = f.read()
    if MARK_START not in text or MARK_END not in text:
        sys.exit("markers absent from README")
    pre, rest = text.split(MARK_START, 1)
    _, post = rest.split(MARK_END, 1)
    new = pre + MARK_START + "\n" + body + MARK_END + post
    if new == text:
        print("unchanged")
        return
    with open(a.readme, "w") as f:
        f.write(new)
    print(f"updated ({len(rows)} rows)")


main()
