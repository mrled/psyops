"""Tests for the user-scoped wallet-backed runtime credential cache."""

import contextlib
import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from roles.urestic.files import uresticcache as cache


class FakeWallet:
    """Keep wallet values and writes in memory without a desktop session."""

    def __init__(self):
        """Initialize an empty wallet with optional injected read failures."""
        self.values = {}
        self.writes = []
        self.fail_on = None

    def get_password(self, service, username):
        """Return a value or simulate a backend failure containing a secret."""
        if username == self.fail_on:
            raise RuntimeError("DO-NOT-LEAK")
        return self.values.get((service, username))

    def set_password(self, service, username, password):
        """Record a wallet update."""
        self.values[service, username] = password
        self.writes.append((service, username, password))


class CacheTests(unittest.TestCase):
    """Exercise CLI behavior against a fake wallet and real private filesystem."""

    def setUp(self):
        """Create an owned runtime directory and inject the explicit backend."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        environment = patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(self.root)})
        environment.start()
        self.addCleanup(environment.stop)
        self.wallet = FakeWallet()
        self.real_backend = cache.wallet_backend
        backend = patch.object(cache, "wallet_backend", return_value=self.wallet)
        self.backend = backend.start()
        self.addCleanup(backend.stop)
        self.credentials = dict.fromkeys(cache.CREDENTIALS, "DO-NOT-LEAK")
        for name, value in self.credentials.items():
            self.wallet.values["psyops.urestic.backup", name] = value

    def run_cli(self, *args, payload=None):
        """Invoke the CLI while capturing every public output stream."""
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps(payload))),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            result = cache.main(list(args))
        self.assertNotIn("DO-NOT-LEAK", stdout.getvalue() + stderr.getvalue())
        return result, stdout.getvalue(), stderr.getvalue()

    def test_store_idempotence_and_update(self):
        """Only differing wallet values should be written."""
        jobs = [{"name": "backup", "credentials": self.credentials}]
        self.assertEqual(self.run_cli("store", payload=jobs), (0, "ok\n", ""))
        self.assertEqual(self.wallet.writes, [])
        self.credentials["restic.password"] = "updated"
        self.assertEqual(self.run_cli("store", payload=jobs), (0, "changed\n", ""))
        self.assertEqual(
            self.wallet.writes, [("psyops.urestic.backup", "restic.password", "updated")]
        )
        self.assertEqual(self.run_cli("store", payload=jobs), (0, "ok\n", ""))

    def test_store_initial_population(self):
        """Provisioning a new job writes each filename under its own service."""
        self.wallet.values.clear()
        jobs = [{"name": "backup", "credentials": self.credentials}]
        self.assertEqual(self.run_cli("store", payload=jobs), (0, "changed\n", ""))
        self.assertEqual(len(self.wallet.writes), 3)
        self.assertEqual(
            self.wallet.values,
            {("psyops.urestic.backup", key): value for key, value in self.credentials.items()},
        )

    def test_backend_is_explicit_secret_service(self):
        """Backend selection constructs Secret Service directly, not keyring's default."""
        from keyring.backends.SecretService import Keyring

        with patch("keyring.backends.SecretService.Keyring", spec=Keyring) as backend:
            self.assertIs(self.real_backend(), backend.return_value)

    def test_unlock_private_and_idempotent(self):
        """Unlock creates private files and leaves identical files untouched."""
        self.assertEqual(self.run_cli("unlock", "backup"), (0, "changed\n", ""))
        directory = self.root / "urestic" / "backup"
        for path in (directory.parent, directory):
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
        snapshots = {}
        for name in cache.CREDENTIALS:
            path = directory / name
            self.assertEqual(path.read_bytes(), b"DO-NOT-LEAK")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            snapshots[name] = path.stat().st_mtime_ns
        self.assertEqual(self.run_cli("unlock", "backup"), (0, "ok\n", ""))
        self.assertEqual(snapshots, {p.name: p.stat().st_mtime_ns for p in directory.iterdir()})
        (directory / "restic.password").chmod(0o644)
        self.assertEqual(self.run_cli("unlock", "backup"), (0, "changed\n", ""))
        self.assertEqual(stat.S_IMODE((directory / "restic.password").stat().st_mode), 0o600)

    def test_directory_permissions_repaired_as_change(self):
        """Repairing directory permissions is also a reported cache change."""
        self.run_cli("unlock", "backup")
        (self.root / "urestic" / "backup").chmod(0o750)
        self.assertEqual(self.run_cli("unlock", "backup"), (0, "changed\n", ""))
        self.assertEqual(self.run_cli("unlock", "backup"), (0, "ok\n", ""))

    def test_wallet_read_failures_preserve_existing_cache(self):
        """All secrets must be read before any runtime file is changed."""
        self.run_cli("unlock", "backup")
        self.wallet.values["psyops.urestic.backup", "restic.password"] = "new"
        key = ("psyops.urestic.backup", cache.CREDENTIALS[-1])
        del self.wallet.values[key]
        for failure in (None, cache.CREDENTIALS[-1]):
            with self.subTest(failure=failure):
                self.wallet.fail_on = failure
                code, output, error = self.run_cli("unlock", "backup")
                self.assertEqual(code, 1)
                self.assertEqual(output, "")
                self.assertTrue(error)
                for path in (self.root / "urestic" / "backup").iterdir():
                    self.assertEqual(path.read_bytes(), b"DO-NOT-LEAK")

    def test_missing_runtime_has_no_fallback(self):
        """Missing runtime configuration fails without wallet access or writes."""
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(self.run_cli("unlock", "backup")[0], 1)
        self.backend.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_invalid_runtime_directory(self):
        """Reject missing, public, symlinked, or foreign-owned runtime roots."""
        self.root.chmod(0o755)
        self.assertEqual(self.run_cli("unlock", "backup")[0], 1)
        self.root.chmod(0o700)
        with patch.object(cache.os, "getuid", return_value=os.getuid() + 1):
            self.assertEqual(self.run_cli("unlock", "backup")[0], 1)
        for path in (self.root / "absent", self.root / "link"):
            if path.name == "link":
                path.symlink_to(self.root, target_is_directory=True)
            with patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(path)}):
                self.assertEqual(self.run_cli("unlock", "backup")[0], 1)

    def test_lock_only_selected_job_and_unsafe_names(self):
        """Lock is scoped to one safe basename and is idempotent."""
        self.run_cli("unlock", "backup")
        other = self.root / "urestic" / "other"
        other.mkdir()
        (other / "keep").write_text("keep")
        for job in ("..", ".", "../other", "/", "", "a/b"):
            self.assertEqual(self.run_cli("lock", job)[0], 1)
        self.assertEqual(self.run_cli("lock", "backup"), (0, "changed\n", ""))
        self.assertEqual((other / "keep").read_text(), "keep")
        self.assertEqual(self.run_cli("lock", "backup"), (0, "ok\n", ""))

    def test_status_never_uses_wallet_or_prints_secrets(self):
        """Status reports only the presence of a ready private cache."""
        self.assertEqual(self.run_cli("status", "backup"), (0, "locked\n", ""))
        self.run_cli("unlock", "backup")
        self.backend.reset_mock()
        self.assertEqual(self.run_cli("status", "backup"), (0, "unlocked\n", ""))
        (self.root / "urestic" / "backup" / cache.CREDENTIALS[0]).unlink()
        self.assertEqual(self.run_cli("status", "backup"), (0, "locked\n", ""))
        self.backend.assert_not_called()

    def test_atomic_failure_cleans_temporary_files(self):
        """Failed replacement does not leak temporary files or exception text."""
        with patch.object(cache.os, "replace", side_effect=OSError("DO-NOT-LEAK")):
            self.assertEqual(self.run_cli("unlock", "backup")[0], 1)
        self.assertEqual(list((self.root / "urestic" / "backup").iterdir()), [])

    def test_symlink_job_does_not_touch_target(self):
        """Cache operations never follow a job-directory symlink."""
        (self.root / "urestic").mkdir(mode=0o700)
        target = self.root / "outside"
        target.mkdir()
        (target / "keep").write_text("keep")
        (self.root / "urestic" / "backup").symlink_to(target, target_is_directory=True)
        for command in ("unlock", "lock"):
            self.assertEqual(self.run_cli(command, "backup")[0], 1)
        self.assertEqual((target / "keep").read_text(), "keep")

    def test_store_failure_sanitized(self):
        """Neither backend failures nor invalid JSON expose input secrets."""
        self.wallet.fail_on = "restic.password"
        jobs = [{"name": "backup", "credentials": self.credentials}]
        self.assertEqual(self.run_cli("store", payload=jobs)[0], 1)
        self.assertEqual(self.run_cli("store", payload="DO-NOT-LEAK")[0], 1)
        self.wallet.fail_on = None
        self.wallet.values.clear()
        with patch.object(self.wallet, "set_password", side_effect=RuntimeError("DO-NOT-LEAK")):
            self.assertEqual(self.run_cli("store", payload=jobs)[0], 1)


if __name__ == "__main__":
    unittest.main()
