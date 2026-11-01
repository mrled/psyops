"""Exercise the betaecan CLI without a wallet or a real repository."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import betaecan


class CliTests(unittest.TestCase):
    """Check discovery, credentials, argument forwarding, and executable behavior."""

    def setUp(self):
        """Create isolated configuration and runtime trees."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = self.root / "config"
        self.config.mkdir()
        self.runtime = self.root / "runtime"
        self.cache = self.runtime / "betaecan" / "daily"
        self.env = {"XDG_RUNTIME_DIR": str(self.runtime), "UNRELATED": "preserved"}

    def job(self, name="daily"):
        """Write one job's public configuration."""
        directory = self.config / name
        directory.mkdir()
        (directory / "restic.repository").write_text("s3:https://example/bucket\n\n")
        (directory / "restic.paths").write_text("/home/user\n/path with spaces\n")

    def unlock(self):
        """Write runtime credentials with shell-cat newline semantics."""
        self.cache.mkdir(parents=True)
        for name, value in {
            "restic.password": "password\n",
            "aws.access-key-id": "access\n\n",
            "aws.secret-access-key": "secret \n\n",
        }.items():
            (self.cache / name).write_text(value)

    def invoke(self, arguments):
        """Run main while collecting its user-facing output."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = betaecan.main(["--config-dir", str(self.config), *arguments])
        return status, out.getvalue(), err.getvalue()

    def test_jobs_without_cache(self):
        """List sorted repositories and source paths without runtime credentials."""
        self.job("z-last")
        self.job("a-first")
        (self.config / "ignored").mkdir()
        with patch.dict(os.environ, {}, clear=True):
            status, out, err = self.invoke(["jobs"])
        self.assertEqual((status, err), (0, ""))
        self.assertLess(out.index("a-first"), out.index("z-last"))
        for value in ("s3:https://example/bucket", "/home/user", "/path with spaces"):
            self.assertIn(value, out)
        self.assertNotIn("ignored", out)
        self.assertNotIn("secret", out)

    def test_empty_and_default_config(self):
        """Use the home-relative default even when XDG_CONFIG_HOME is set."""
        out = io.StringIO()
        with (
            patch("betaecan.Path.home", return_value=self.root),
            patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.config)}),
            contextlib.redirect_stdout(out),
        ):
            self.assertEqual(betaecan.main(["jobs"]), 0)
        self.assertIn("No jobs", out.getvalue())
        self.assertIn(str(self.root / ".config/psyops/backup"), out.getvalue())

    def test_exact_environment_and_passthrough(self):
        """Forward all restic arguments and replace only conflicting environment values."""
        self.job()
        self.unlock()
        (self.config / "daily" / "restic.repository").write_bytes(
            b"s3:https://example/bucket\r\n\n"
        )
        inherited = {
            **self.env,
            "RESTIC_REPOSITORY": "old",
            "RESTIC_PASSWORD_FILE": "old",
            "AWS_ACCESS_KEY_ID": "old",
            "AWS_SECRET_ACCESS_KEY": "old",
            **dict.fromkeys(
                (
                    "RESTIC_PASSWORD",
                    "RESTIC_PASSWORD_COMMAND",
                    "RESTIC_REPOSITORY_FILE",
                    "AWS_SESSION_TOKEN",
                    "AWS_SECURITY_TOKEN",
                ),
                "stale",
            ),
        }
        expected = {
            **self.env,
            "RESTIC_REPOSITORY": "s3:https://example/bucket\r",
            "RESTIC_PASSWORD_FILE": str(self.cache / "restic.password"),
            "AWS_ACCESS_KEY_ID": "access",
            "AWS_SECRET_ACCESS_KEY": "secret ",
        }
        for arguments in (
            ["snapshots", "--json"],
            ["--help"],
            ["restore", "latest", "--target", "/restore with spaces", "--include", "-literal"],
        ):
            with (
                self.subTest(arguments=arguments),
                patch.dict(os.environ, inherited, clear=True),
                patch("betaecan.os.execvpe") as execute,
            ):
                self.assertEqual(self.invoke(["restic", "daily", *arguments]), (0, "", ""))
                execute.assert_called_once_with("restic", ["restic", *arguments], expected)

    def test_missing_job_and_invalid_names(self):
        """Reject absent jobs and names that can escape the configuration directory."""
        for name in ("missing", "..", ".", "../daily", "a/b", "/tmp/job"):
            with self.subTest(name=name), patch.dict(os.environ, self.env, clear=True):
                status, out, err = self.invoke(["restic", name, "snapshots"])
                self.assertNotEqual(status, 0)
                self.assertEqual(out, "")
                self.assertIn("betaecan:", err)
                self.assertNotIn("Traceback", err)

    def test_missing_cache(self):
        """Fail promptly with unlock guidance for every missing credential or runtime root."""
        self.job()
        self.unlock()
        cases = [None, "restic.password", "aws.access-key-id", "aws.secret-access-key"]
        for missing in cases:
            with self.subTest(missing=missing):
                credential = self.cache / missing if missing else None
                contents = credential.read_bytes() if credential else None
                if credential:
                    credential.unlink()
                try:
                    with (
                        patch.dict(os.environ, self.env if missing else {}, clear=True),
                        patch("betaecan.os.execvpe") as execute,
                    ):
                        status, out, err = self.invoke(["restic", "daily", "snapshots"])
                    self.assertNotEqual(status, 0)
                    self.assertEqual(out, "")
                    self.assertIn("betaecancache unlock daily", err)
                    self.assertNotIn("secret", err)
                    execute.assert_not_called()
                finally:
                    if credential and contents is not None:
                        credential.write_bytes(contents)

    def test_sanitized_config_and_credential_errors(self):
        """Hide exception details that might contain secrets."""
        self.job()
        self.unlock()
        for error in (OSError("sensitive-value"), UnicodeError("sensitive-value")):
            with (
                self.subTest(error=type(error)),
                patch.dict(os.environ, self.env),
                patch("betaecan.Path.open", side_effect=error),
            ):
                status, _, err = self.invoke(["restic", "daily", "snapshots"])
                self.assertNotEqual(status, 0)
                self.assertNotIn("sensitive-value", err)
                self.assertNotIn("Traceback", err)

    def test_missing_restic(self):
        """Report a missing restic executable with the conventional exit status."""
        self.job()
        self.unlock()
        with (
            patch.dict(os.environ, self.env),
            patch("betaecan.os.execvpe", side_effect=FileNotFoundError("sensitive-value")),
        ):
            status, _, err = self.invoke(["restic", "daily", "snapshots"])
        self.assertEqual(status, 127)
        self.assertIn("restic", err)
        self.assertNotIn("sensitive-value", err)
        result = subprocess.run(
            [
                sys.executable,
                betaecan.__file__,
                "--config-dir",
                str(self.config),
                "restic",
                "daily",
                "snapshots",
            ],
            env={**os.environ, **self.env, "PATH": str(self.root / "absent")},
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(result.returncode, 127)
        self.assertEqual(result.stdout, "")
        self.assertIn("restic executable not found", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_real_cli_exec_streams_and_exit_status(self):
        """Run module and copied standalone entry points against a real fake-restic process."""
        self.job()
        self.unlock()
        binary = self.root / "bin"
        binary.mkdir()
        restic = binary / "restic"
        restic.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "print(json.dumps(sys.argv[1:]), flush=True)\n"
            "print(os.environ['AWS_SECRET_ACCESS_KEY'], flush=True)\n"
            "sys.stdin.readline()\n"
            "sys.exit(23)\n"
        )
        restic.chmod(0o755)
        standalone = binary / "betaecan"
        shutil.copyfile(betaecan.__file__, standalone)
        standalone.chmod(0o755)
        commands = [[sys.executable, "-m", "betaecan"], [str(standalone)]]
        for command in commands:
            with self.subTest(command=command):
                process = subprocess.Popen(
                    [
                        *command,
                        "--config-dir",
                        str(self.config),
                        "restic",
                        "daily",
                        "restore",
                        "latest",
                        "--target",
                        "/path with spaces",
                    ],
                    env={**os.environ, **self.env, "PATH": str(binary)},
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.addCleanup(lambda p=process: p.poll() is None and p.kill())
                assert process.stdout is not None
                self.assertEqual(
                    json.loads(process.stdout.readline()),
                    ["restore", "latest", "--target", "/path with spaces"],
                )
                self.assertEqual(process.stdout.readline(), "secret \n")
                _, err = process.communicate("continue\n", timeout=5)
                self.assertEqual((process.returncode, err), (23, ""))


if __name__ == "__main__":
    unittest.main()
