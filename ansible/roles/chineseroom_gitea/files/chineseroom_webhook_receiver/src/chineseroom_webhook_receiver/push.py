"""Push a branch from Gitea (origin) to GitHub."""
import logging
from pathlib import Path

from chineseroom_webhook_receiver._git import run_git, run_lfs

log = logging.getLogger(__name__)


def do_push(repo, ref, mirrors_dir):
    """Fetch a branch from Gitea and push it to GitHub, including LFS objects.

    Concurrency is managed by the caller (RepoJobManager); no locking is done here.
    """
    tag = f"[{repo}]"
    branch = ref.removeprefix("refs/heads/")
    mirror_dir = Path(mirrors_dir) / repo

    if not (mirror_dir / ".git").is_dir():
        raise RuntimeError(f"{tag} working clone not found: {mirror_dir}")

    log.info("%s fetching %s from Gitea", tag, branch)
    run_git(mirror_dir, "fetch", "origin", f"refs/heads/{branch}:refs/remotes/origin/{branch}")

    log.info("%s fetching LFS objects from Gitea", tag)
    run_lfs(mirror_dir, "fetch", "origin", "--all")

    log.info("%s pushing %s to GitHub", tag, branch)
    run_git(mirror_dir, "push", "github", f"refs/remotes/origin/{branch}:refs/heads/{branch}")

    log.info("%s pushing LFS objects to GitHub", tag)
    run_lfs(mirror_dir, "push", "github", "--all")

    log.info("%s push complete", tag)
