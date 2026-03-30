"""
Pull changes from GitHub into Gitea.

sync_repo() and related functions contain the git logic and are called directly
by the webhook receiver process (server.py).

The chineseroom-pull-from-github console script (main()) is a thin HTTP client
that asks the webhook receiver to schedule a pull, so all git operations are
serialized through the receiver's RepoJobManager regardless of whether a pull
was triggered by the timer or by a /pull-sync webhook.
"""
import argparse
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from chineseroom_webhook_receiver._git import run_git, run_lfs

log = logging.getLogger(__name__)


def load_config(path):
    with open(path) as f:
        return json.load(f)


def get_mirror_repos(gitea_url, gitea_org, token):
    """Yield repo names from the mirror org, handling pagination."""
    page = 1
    while True:
        url = f"{gitea_url}/api/v1/orgs/{gitea_org}/repos?limit=50&page={page}"
        req = urllib.request.Request(url, headers={"Authorization": f"token {token}"})
        with urllib.request.urlopen(req) as resp:
            repos = json.load(resp)
        if not repos:
            break
        for r in repos:
            yield r["name"]
        page += 1


def gitea_api(gitea_url, token, method, path, body=None):
    """Make a Gitea API request. Returns the parsed JSON response.
    Raises RuntimeError with full HTTP status and response body on non-2xx responses.
    """
    url = f"{gitea_url}/api/v1{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": f"token {token}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        raise RuntimeError(f"Gitea API {method} {path} -> HTTP {exc.code} {exc.reason}: {body_text}") from exc


def github_default_branch_from_remote(mirror_dir):
    """Return the default branch by querying the github remote via SSH (no API token needed).

    Runs 'git ls-remote --symref github HEAD' which returns a symref line like:
        ref: refs/heads/main\tHEAD
    """
    result = run_git(mirror_dir, "ls-remote", "--symref", "github", "HEAD", fatal=False)
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        m = re.match(r"^ref: refs/heads/(\S+)\s+HEAD$", line)
        if m:
            return m.group(1)
    return None


def sync_default_branch(gitea_url, gitea_org, repo, mirror_token, mirror_dir):
    """Set the Gitea repo default branch to match GitHub's if it has changed."""
    tag = f"[{repo}]"

    gh_default = github_default_branch_from_remote(mirror_dir)
    if not gh_default:
        log.warning("%s could not determine GitHub default branch; skipping", tag)
        return

    log.info("%s GitHub default branch: %s", tag, gh_default)
    gitea_default = gh_default

    try:
        info = gitea_api(gitea_url, mirror_token, "GET", f"/repos/{gitea_org}/{repo}")
        current = info["default_branch"]
        if current == gitea_default:
            log.info("%s Gitea default branch already %s; no change needed", tag, gitea_default)
            return
        log.info("%s updating Gitea default branch: %s -> %s", tag, current, gitea_default)
        gitea_api(gitea_url, mirror_token, "PATCH", f"/repos/{gitea_org}/{repo}", {"default_branch": gitea_default})
        log.info("%s Gitea default branch updated to %s", tag, gitea_default)
    except RuntimeError as exc:
        log.warning("%s failed to update Gitea default branch: %s", tag, exc)


def sync_repo(repo, config, token):
    mirrors_dir = config["mirrors_dir"]
    mirror_dir = Path(mirrors_dir) / repo
    tag = f"[{repo}]"

    if not (mirror_dir / ".git").is_dir():
        log.warning("%s working clone not found; skipping", tag)
        return

    try:
        log.info("%s fetching branches from GitHub", tag)
        run_git(mirror_dir, "fetch", "github", "+refs/heads/*:refs/remotes/github/*", "--prune")

        log.info("%s fetching tags from GitHub", tag)
        run_git(mirror_dir, "fetch", "github", "+refs/tags/*:refs/tags/*")

        log.info("%s fetching LFS objects from GitHub", tag)
        run_lfs(mirror_dir, "fetch", "github", "--all")

        log.info("%s pushing branches to Gitea", tag)
        run_git(mirror_dir, "push", "origin", "+refs/remotes/github/*:refs/heads/*", "--prune")

        log.info("%s pushing tags to Gitea", tag)
        run_git(mirror_dir, "push", "origin", "+refs/tags/*:refs/tags/*")

        log.info("%s pushing LFS objects to Gitea", tag)
        run_lfs(mirror_dir, "push", "origin", "--all")

        sync_default_branch(config["gitea_url"], config["gitea_org"], repo, token, mirror_dir)

        log.info("%s sync complete", tag)

    except RuntimeError as exc:
        log.error("%s sync aborted: %s", tag, exc)


def main():
    """HTTP client entry point: ask the webhook receiver to schedule a pull."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Trigger a GitHub pull via the webhook receiver.")
    parser.add_argument("--repo", metavar="REPO", help="Pull only this repo (default: all repos)")
    args = parser.parse_args()

    host = os.environ.get("GITEA_WEBHOOK_LISTEN", "127.0.0.1")
    port = int(os.environ.get("GITEA_WEBHOOK_PORT", "9420"))

    if args.repo:
        url = f"http://{host}:{port}/pull-sync"
        body = json.dumps({"repo": args.repo}).encode()
    else:
        url = f"http://{host}:{port}/pull-all"
        body = b""

    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            sys.stdout.write(resp.read().decode())
    except urllib.error.URLError as exc:
        log.error("Failed to contact webhook receiver at %s: %s", url, exc)
        sys.exit(1)
