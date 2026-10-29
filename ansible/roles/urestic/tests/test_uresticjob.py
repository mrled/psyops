"""Exercise the real uresticjob shell script without restic or system credentials."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import TypedDict, cast
from unittest.mock import patch


class ResticCall(TypedDict):
    """Describe arguments and credential environment recorded by fake restic."""

    args: list[str]
    env: dict[str, str]


FAKE_RESTIC = """\
import json
import os
import sys

command = sys.argv[1]
with open(os.environ["RESTIC_MOCK_LOG"], "a") as log:
    log.write(json.dumps({
        "args": sys.argv[1:],
        "env": {name: os.environ[name] for name in (
            "RESTIC_PASSWORD_FILE", "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY", "RESTIC_REPOSITORY",
        )},
    }) + "\\n")
if command == "cat":
    print("repository config")
sys.exit(int(os.environ.get("RESTIC_MOCK_" + command.upper() + "_STATUS", "0")))
"""


class UresticjobTests(unittest.TestCase):
    """Verify shell-wrapper command routing, credential loading, and exit statuses."""

    def setUp(self) -> None:
        """Build isolated credentials, job files, and a wrapper using a logging fake restic."""
        temporary = tempfile.TemporaryDirectory(prefix="uresticjob-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        # Spaces exercise quoting of both executable and configuration paths.
        self.job = self.directory / "backup job"
        self.job.mkdir()
        self.runtime = self.directory / "runtime"
        self.credentials = self.runtime / "urestic" / self.job.name
        self.credentials.mkdir(parents=True)
        for name, value in {
            "restic.password": "test password\n",
            "aws.access-key-id": "test access key\n",
            "aws.secret-access-key": "test secret key\n",
        }.items():
            (self.credentials / name).write_text(value)
        (self.job / "restic.repository").write_text("s3:example.invalid/bucket/repo\n")
        (self.job / "restic.paths").write_text("/some path\n")
        (self.job / "restic.excludes").write_text("*.tmp\n")
        fake = self.directory / "fake restic"
        fake.write_text(f"#!{sys.executable}\n" + FAKE_RESTIC)
        fake.chmod(0o700)
        source = Path(__file__).resolve().parents[1] / "files" / "uresticjob"
        self.script = self.directory / "uresticjob"
        # The only source transformation is redirecting the absolute executable.
        self.script.write_text(source.read_text().replace("/usr/bin/restic", f'"{fake}"'))
        self.log = self.directory / "restic.jsonl"

    def run_job(
        self, *args: str, cat_status: int = 0, init_status: int = 0, backup_status: int = 0
    ) -> tuple[subprocess.CompletedProcess[str], list[ResticCall]]:
        """Run the wrapper with injected statuses and verify credentials and output handling."""
        self.log.unlink(missing_ok=True)
        result = subprocess.run(
            ["/bin/sh", str(self.script), str(self.job), *args],
            env={
                **os.environ,
                "XDG_RUNTIME_DIR": str(self.runtime),
                "RESTIC_MOCK_LOG": str(self.log),
                "RESTIC_MOCK_CAT_STATUS": str(cat_status),
                "RESTIC_MOCK_INIT_STATUS": str(init_status),
                "RESTIC_MOCK_BACKUP_STATUS": str(backup_status),
            },
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        calls = (
            [cast(ResticCall, json.loads(line)) for line in self.log.read_text().splitlines()]
            if self.log.exists()
            else []
        )
        expected_env = {
            "RESTIC_PASSWORD_FILE": str(self.credentials / "restic.password"),
            "AWS_ACCESS_KEY_ID": "test access key",
            "AWS_SECRET_ACCESS_KEY": "test secret key",
            "RESTIC_REPOSITORY": "s3:example.invalid/bucket/repo",
        }
        for call in calls:
            self.assertEqual(call["env"], expected_env)
        # Only the backup probe suppresses cat's output; explicit cat is passed through.
        self.assertEqual(result.stdout, "repository config\n" if args[0] == "cat" else "")
        return result, calls

    def backup_args(self, *extra: str) -> list[str]:
        """Build expected backup arguments from job paths and caller-supplied options."""
        return [
            "backup",
            "--exclude-caches",
            "--files-from-verbatim",
            str(self.job / "restic.paths"),
            "--exclude-file",
            str(self.job / "restic.excludes"),
            *extra,
        ]

    def test_locked_cache_stops_before_accessing_the_repository(self) -> None:
        """Missing runtime credentials fail promptly, without wallet access or repository init."""
        (self.credentials / "restic.password").unlink()
        result, calls = self.run_job("backup", cat_status=10)
        self.assertEqual(result.returncode, 1)
        self.assertIn("credentials locked", result.stderr)
        self.assertEqual(calls, [])

    def test_failed_cache_read_stops_before_accessing_the_repository(self) -> None:
        """A read failure after the readiness check must not become an empty credential."""
        commands = self.directory / "commands"
        commands.mkdir()
        failing_cat = commands / "cat"
        failing_cat.write_text("#!/bin/sh\nexit 1\n")
        failing_cat.chmod(0o700)
        with patch.dict(os.environ, {"PATH": f"{commands}:{os.environ['PATH']}"}):
            result, calls = self.run_job("backup", cat_status=10)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(calls, [])

    def test_existing_repository_skips_init_and_forwards_backup_arguments(self) -> None:
        """A successful probe skips initialization and preserves backup argument boundaries."""
        extra = ("--tag", "nightly backup", "--verbose")
        result, calls = self.run_job("backup", *extra)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            [call["args"] for call in calls], [["cat", "config"], self.backup_args(*extra)]
        )

    def test_missing_repository_initializes_before_backup(self) -> None:
        """Probe status 10 triggers initialization before backup."""
        result, calls = self.run_job("backup", cat_status=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            [call["args"] for call in calls],
            [["cat", "config"], ["init"], self.backup_args()],
        )

    def test_probe_errors_preserve_status_without_init_or_backup(self) -> None:
        """Probe failures other than status 10 stop execution with the original status."""
        # Access/network failure, repository locked, and wrong password.
        for status in (1, 11, 12):
            with self.subTest(status=status):
                result, calls = self.run_job("backup", cat_status=status)
                self.assertEqual(result.returncode, status)
                self.assertEqual([call["args"] for call in calls], [["cat", "config"]])

    def test_init_errors_preserve_status_without_backup(self) -> None:
        """Failed initialization prevents backup and propagates its exit status."""
        result, calls = self.run_job("backup", cat_status=10, init_status=1)
        self.assertEqual(result.returncode, 1)
        self.assertEqual([call["args"] for call in calls], [["cat", "config"], ["init"]])

    def test_backup_partial_failure_preserves_exit_three(self) -> None:
        """Backup status 3 survives whether the repository existed or needed initialization."""
        for cat_status in (0, 10):
            with self.subTest(cat_status=cat_status):
                result, calls = self.run_job("backup", cat_status=cat_status, backup_status=3)
                self.assertEqual(result.returncode, 3)
                expected = [["cat", "config"]]
                if cat_status == 10:
                    expected.append(["init"])
                expected.append(self.backup_args())
                self.assertEqual([call["args"] for call in calls], expected)

    def test_nonbackup_commands_are_forwarded_without_probe_or_auto_init(self) -> None:
        """Other commands retain their arguments and status without automatic repository setup."""
        for args in (
            ("snapshots", "--json"),
            ("init",),
            ("cat", "config"),
        ):
            with self.subTest(args=args):
                result, calls = self.run_job(*args, cat_status=10, init_status=12)
                expected_status = {"cat": 10, "init": 12}.get(args[0], 0)
                self.assertEqual(result.returncode, expected_status)
                self.assertEqual([call["args"] for call in calls], [list(args)])


if __name__ == "__main__":
    unittest.main()
