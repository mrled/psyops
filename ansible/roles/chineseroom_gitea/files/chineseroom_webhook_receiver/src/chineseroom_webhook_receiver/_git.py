"""Shared helpers for running git and git-lfs subprocesses."""
import logging
import subprocess

log = logging.getLogger(__name__)


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
