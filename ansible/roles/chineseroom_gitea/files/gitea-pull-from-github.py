#!/usr/bin/env python3
"""
Pull changes from GitHub into Gitea for all repos in the mirror org.
Run periodically by the gitea-pull-from-github.timer systemd timer.

GitHub branches are mapped to the protected/* namespace in Gitea:
  GitHub refs/heads/foo  ->  Gitea refs/heads/protected/foo

GitHub tags are copied verbatim with force-overwrite:
  GitHub refs/tags/v1.0  ->  Gitea refs/tags/v1.0

The mirror org is queried via the Gitea API on each run, so newly added repos
are picked up automatically without re-running Ansible.

Usage: pull-from-github.py <config-file>
"""
import argparse
import json
import logging
import subprocess
import sys
import urllib.request
from pathlib import Path

log = logging.getLogger("gitea-pull")


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


def run_git(mirror_dir, *args, fatal=True):
    """Run a git command in mirror_dir. Returns CompletedProcess; raises on failure if fatal=True."""
    cmd = ["git", "-C", str(mirror_dir), *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        msg = f"git {args[0]} failed (exit {result.returncode}): {result.stderr.strip()}"
        if fatal:
            raise RuntimeError(msg)
        log.warning(msg)
    return result


def run_lfs(mirror_dir, *args):
    """Run a git-lfs command in mirror_dir. Never fatal — LFS errors are logged and skipped."""
    cmd = ["git", "-C", str(mirror_dir), "lfs", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.warning("git lfs %s failed (non-fatal): %s", args[0], result.stderr.strip())
    return result


def sync_repo(repo, mirrors_dir):
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

        log.info("%s pushing branches to Gitea as protected/*", tag)
        run_git(mirror_dir, "push", "origin", "+refs/remotes/github/*:refs/heads/protected/*", "--prune")

        log.info("%s pushing tags to Gitea", tag)
        run_git(mirror_dir, "push", "origin", "+refs/tags/*:refs/tags/*")

        log.info("%s pushing LFS objects to Gitea", tag)
        run_lfs(mirror_dir, "push", "origin", "--all")

        log.info("%s sync complete", tag)

    except RuntimeError as exc:
        log.error("%s sync aborted: %s", tag, exc)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("config", metavar="CONFIG", help="Path to pull-from-github.conf JSON config file")
    args = parser.parse_args()

    config = load_config(args.config)
    token = Path(config["mirror_token_file"]).read_text().strip()

    for repo in get_mirror_repos(config["gitea_url"], config["gitea_org"], token):
        sync_repo(repo, config["mirrors_dir"])


if __name__ == "__main__":
    main()
