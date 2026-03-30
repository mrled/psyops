"""
Gitea webhook receiver — bidirectional sync between Gitea and GitHub.

Endpoints:

  POST /push-sync  — triggered by Gitea webhook on branch push
      Body: standard Gitea push webhook JSON
      Effect: schedules a push of the branch to GitHub

  POST /pull-sync  — on-demand pull from GitHub for a single repo
      Body: {"repo": "<mirror-repo-name>"}
      Effect: schedules a pull of that repo from GitHub

The receiver listens on localhost only, so no authentication is required.
Every request returns 200 immediately. The actual git operations run in
background threads with dirty-flag semantics per repo: if a new request
arrives while an operation is already in-flight for that repo, it is queued
and executed immediately after the current operation finishes.

Coalescing rules:
  - Multiple pending pushes to the same branch collapse to one push.
  - Multiple pending pushes to different branches are each queued.
  - Multiple pending pulls collapse to one pull.
  - When both pushes and a pull are pending, pushes run first (flush
    Gitea -> GitHub before syncing GitHub -> Gitea).

Gitea must be configured to send a push webhook to:
  http://127.0.0.1:$GITEA_WEBHOOK_PORT/push-sync

To trigger a pull on demand:
  curl -X POST http://127.0.0.1:$GITEA_WEBHOOK_PORT/pull-sync \\
    -H "Content-Type: application/json" \\
    -d '{"repo": "github--owner--reponame"}'
"""
import http.server
import json
import logging
import os
import threading
from pathlib import Path

from chineseroom_webhook_receiver import pull, push

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

PULL_CONFIG = os.environ["GITEA_PULL_CONFIG"]
MIRRORS_DIR = os.environ["GITEA_MIRRORS_DIR"]
HOST = os.environ.get("GITEA_WEBHOOK_LISTEN", "127.0.0.1")
PORT = int(os.environ.get("GITEA_WEBHOOK_PORT", "9420"))

_pull_config = pull.load_config(PULL_CONFIG)
_pull_token = Path(_pull_config["mirror_token_file"]).read_text().strip()


def do_push(repo, ref):
    push.do_push(repo, ref, MIRRORS_DIR)


def do_pull(repo):
    pull.sync_repo(repo, _pull_config, _pull_token)


class RepoJobManager:
    """
    Per-repo serialized job queue with dirty-flag coalescing.

    At most one worker thread runs per repo at a time. Requests that arrive
    while a worker is in-flight are accumulated as pending work. When the worker
    finishes it atomically picks up all pending work and, if any exists, spawns
    a single follow-up thread to handle it.

    All state mutations are protected by self._lock. The lock is never held
    during blocking I/O.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._active = {}          # repo -> bool
        self._pending_pushes = {}  # repo -> set[ref]
        self._pending_pull = {}    # repo -> bool

    def schedule_push(self, repo, ref):
        with self._lock:
            if not self._active.get(repo):
                self._active[repo] = True
                self._spawn(repo, pushes={ref}, pull=False)
            else:
                self._pending_pushes.setdefault(repo, set()).add(ref)

    def schedule_pull(self, repo):
        with self._lock:
            if not self._active.get(repo):
                self._active[repo] = True
                self._spawn(repo, pushes=set(), pull=True)
            else:
                self._pending_pull[repo] = True

    def _spawn(self, repo, pushes, pull):
        """Start a worker thread. Must be called with self._lock held."""
        t = threading.Thread(
            target=self._worker,
            args=(repo, set(pushes), pull),
            daemon=True,
        )
        t.start()

    def _worker(self, repo, pushes, pull):
        try:
            for ref in sorted(pushes):
                try:
                    do_push(repo, ref)
                except Exception:
                    log.exception("[%s] unexpected error during push of %s", repo, ref)
            if pull:
                try:
                    do_pull(repo)
                except Exception:
                    log.exception("[%s] unexpected error during pull", repo)
        finally:
            self._finish(repo)

    def _finish(self, repo):
        """Pick up pending work or mark repo idle. Called from worker thread."""
        with self._lock:
            pushes = self._pending_pushes.pop(repo, set())
            pull = self._pending_pull.pop(repo, False)
            if pushes or pull:
                self._spawn(repo, pushes=pushes, pull=pull)
            else:
                self._active.pop(repo, None)


_jobs = RepoJobManager()


class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._reply(400, b"bad json\n")
            return

        if self.path == "/push-sync":
            self._handle_push(payload)
        elif self.path == "/pull-sync":
            self._handle_pull(payload)
        else:
            self._reply(404, b"not found\n")

    def _handle_push(self, payload):
        ref = payload.get("ref", "")
        repo_name = payload.get("repository", {}).get("name", "")
        log.info("Push event: repo=%s ref=%s", repo_name, ref)

        mirror_dir = os.path.join(MIRRORS_DIR, repo_name)
        auto_push_marker = os.path.join(mirror_dir, ".git", "gitea", "auto-push")

        if not os.path.isdir(mirror_dir):
            self._reply(200, b"no mirror configured\n")
            return
        if not os.path.exists(auto_push_marker):
            self._reply(200, b"auto-push disabled\n")
            return
        if not ref.startswith("refs/heads/"):
            log.info("Ref %s is not a branch; skipping", ref)
            self._reply(200, b"not a branch\n")
            return

        log.info("Scheduling push: %s:%s", repo_name, ref)
        _jobs.schedule_push(repo_name, ref)
        self._reply(200, b"push scheduled\n")

    def _handle_pull(self, payload):
        repo_name = payload.get("repo", "")
        if not repo_name:
            self._reply(400, b"missing repo\n")
            return

        mirror_dir = os.path.join(MIRRORS_DIR, repo_name)
        if not os.path.isdir(mirror_dir):
            self._reply(200, b"no mirror configured\n")
            return

        log.info("Scheduling pull: %s", repo_name)
        _jobs.schedule_pull(repo_name)
        self._reply(200, b"pull scheduled\n")

    def _reply(self, code, body):
        self.send_response(code)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        log.debug("%s - %s", self.address_string(), format % args)


def main():
    server = http.server.ThreadingHTTPServer((HOST, PORT), WebhookHandler)
    log.info("Listening on %s:%d", HOST, PORT)
    server.serve_forever()
