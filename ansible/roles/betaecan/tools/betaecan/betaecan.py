#!/usr/bin/python3
"""Inspect backups and run restic using credentials managed by the betaecan role."""

import argparse
import os
import sys
from pathlib import Path


class CliError(Exception):
    """Represent a safe, user-facing configuration or credential error."""


def job_name(value: str) -> str:
    """Require a single job basename rather than a path."""
    if not value or value in (".", "..") or "/" in value or "\0" in value:
        raise CliError("job must be a single directory name")
    return value


def read_value(path: Path) -> str:
    """Read a value with the trailing-newline behavior of shell command substitution."""
    with path.open(encoding="utf-8", newline="") as stream:
        return stream.read().rstrip("\n")


def list_jobs(config: Path) -> None:
    """Show public job configuration without accessing the credential cache."""
    try:
        directories = sorted(config.iterdir()) if config.exists() else []
        jobs = [
            path for path in directories if path.is_dir() and (path / "restic.repository").is_file()
        ]
        if not jobs:
            print(f"No jobs found in {config}")
        for directory in jobs:
            repository = read_value(directory / "restic.repository")
            paths = (directory / "restic.paths").read_text(encoding="utf-8").splitlines()
            print(f"{directory.name}\n  Repository: {repository}\n  Source paths:")
            for path in paths:
                print(f"    {path}")
    except (OSError, UnicodeError):
        raise CliError("cannot read job configuration") from None


def restic_environment(config: Path, job: str) -> dict[str, str]:
    """Load only the configured repository and already-unlocked runtime credentials."""
    job_name(job)
    try:
        repository = read_value(config / job / "restic.repository")
    except (OSError, UnicodeError):
        raise CliError(f"cannot read repository configuration for job {job}") from None

    guidance = f"credentials unavailable; run betaecancache unlock {job}"
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime:
        raise CliError(guidance)
    cache = Path(runtime) / "betaecan" / job
    try:
        password = cache / "restic.password"
        with password.open("rb") as stream:
            stream.read(1)
        access_key = read_value(cache / "aws.access-key-id")
        secret_key = read_value(cache / "aws.secret-access-key")
    except (OSError, UnicodeError):
        raise CliError(guidance) from None

    env = os.environ.copy()
    for name in (
        "RESTIC_PASSWORD",
        "RESTIC_PASSWORD_COMMAND",
        "RESTIC_REPOSITORY_FILE",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
    ):
        env.pop(name, None)
    env.update(
        RESTIC_REPOSITORY=repository,
        RESTIC_PASSWORD_FILE=str(password),
        AWS_ACCESS_KEY_ID=access_key,
        AWS_SECRET_ACCESS_KEY=secret_key,
    )
    return env


def main(argv: list[str] | None = None) -> int:
    """Parse the public CLI and replace this process with restic when requested."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=Path.home() / ".config/psyops/backup",
        help="job configuration directory (default: ~/.config/psyops/backup)",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("jobs", help="list configured jobs and source paths")
    restic = commands.add_parser("restic", help="run restic with a job's cached credentials")
    restic.add_argument("job", help="configured job name")
    restic.add_argument("arguments", nargs=argparse.REMAINDER, help="arguments passed to restic")
    args = parser.parse_args(argv)
    try:
        if args.command == "jobs":
            list_jobs(args.config_dir)
        else:
            env = restic_environment(args.config_dir, args.job)
            try:
                os.execvpe("restic", ["restic", *args.arguments], env)
            except FileNotFoundError:
                print("betaecan: restic executable not found in PATH", file=sys.stderr)
                return 127
            except (OSError, ValueError):
                raise CliError(
                    "cannot execute restic; check executable and configuration"
                ) from None
    except CliError as error:
        print(f"betaecan: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
