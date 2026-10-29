#!/usr/bin/python3
# Installed by the urestic Ansible role.
"""Store credentials in the desktop wallet and cache them in the user's runtime directory."""

import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

CREDENTIALS = ("restic.password", "aws.access-key-id", "aws.secret-access-key")


class CacheError(Exception):
    """A safe diagnostic that never includes credentials or backend exception text."""


def wallet_backend():
    """Select Secret Service explicitly, never the configured fallback backend."""
    from keyring.backends.SecretService import Keyring

    return Keyring()


def validate_job(job: str) -> str:
    """Require one basename so cache operations cannot escape their job directory."""
    if not job or job in (".", "..") or "/" in job or "\x00" in job:
        raise CacheError("JOB must be a nonempty basename")
    return job


def runtime_root() -> Path:
    """Require an existing, owned, private runtime root without any fallback."""
    value = os.environ.get("XDG_RUNTIME_DIR")
    if not value or not Path(value).is_absolute():
        raise CacheError("XDG_RUNTIME_DIR must name an existing private runtime directory")
    root = Path(value)
    try:
        info = root.lstat()
    except OSError:
        raise CacheError("XDG_RUNTIME_DIR is unavailable") from None
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise CacheError("XDG_RUNTIME_DIR must be an owned directory with mode 0700")
    return root


def cache_directory(root: Path, job: str, create: bool = False) -> tuple[Path, bool]:
    """Check cache directories without following symlinks, optionally creating them."""
    directory = root
    changed = False
    for part in ("urestic", job):
        directory = directory / part
        if create:
            try:
                directory.mkdir(mode=0o700)
                changed = True
            except FileExistsError:
                pass
        try:
            info = directory.lstat()
        except FileNotFoundError:
            if not create:
                return root / "urestic" / job, changed
            raise
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise CacheError("Cache directory must be an owned directory, not a symlink")
        if create and stat.S_IMODE(info.st_mode) != 0o700:
            directory.chmod(0o700)
            changed = True
        elif stat.S_IMODE(info.st_mode) != 0o700:
            raise CacheError("Cache directory must have mode 0700")
    return directory, changed


def store(payload: object) -> bool:
    """Validate provisioning input and update only changed Secret Service entries."""
    if not isinstance(payload, list):
        raise CacheError("store requires a JSON list of jobs")
    jobs: list[tuple[str, dict[str, str]]] = []
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise CacheError("Each job requires a name and credentials mapping")
        job = validate_job(item["name"])
        credentials = item.get("credentials")
        if (
            not isinstance(credentials, dict)
            or set(credentials) != set(CREDENTIALS)
            or not all(isinstance(value, str) for value in credentials.values())
        ):
            raise CacheError("Each job requires all three string credentials")
        jobs.append((job, credentials))
    changed = False
    try:
        wallet = wallet_backend()
        for job, credentials in jobs:
            for filename, value in credentials.items():
                service = f"psyops.urestic.{job}"
                if wallet.get_password(service, filename) != value:
                    wallet.set_password(service, filename, value)
                    changed = True
    except Exception:
        raise CacheError(
            "Secret Service store failed; check the desktop wallet is available"
        ) from None
    return changed


def ready_file(path: Path) -> bool:
    """Check that a credential is an owned, private regular file without reading it."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return (
        stat.S_ISREG(info.st_mode)
        and info.st_uid == os.getuid()
        and stat.S_IMODE(info.st_mode) == 0o600
    )


def write_credential(path: Path, value: bytes) -> bool:
    """Atomically replace a changed credential using a private runtime-only temporary file."""
    if ready_file(path) and path.read_bytes() == value:
        return False
    descriptor, temporary = tempfile.mkstemp(prefix=".credential-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(value)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True


def unlock(root: Path, job: str) -> bool:
    """Fetch every wallet value before touching the cache, then publish private files."""
    values: dict[str, bytes] = {}
    try:
        wallet = wallet_backend()
        for filename in CREDENTIALS:
            value = wallet.get_password(f"psyops.urestic.{job}", filename)
            if value is None:
                raise CacheError("Wallet is missing a required credential; run store first")
            values[filename] = value.encode("utf-8")
    except CacheError:
        raise
    except Exception:
        raise CacheError(
            "Secret Service read failed; check the desktop wallet is unlocked"
        ) from None
    directory, changed = cache_directory(root, job, create=True)
    for filename, value in values.items():
        if write_credential(directory / filename, value):
            changed = True
    return changed


def main(argv: list[str] | None = None) -> int:
    """Run the CLI with sanitized diagnostics and no secret-bearing exception output."""
    args = sys.argv[1:] if argv is None else argv
    try:
        if args == ["store"]:
            try:
                payload = json.load(sys.stdin)
            except (ValueError, UnicodeError):
                raise CacheError("store requires valid JSON on stdin") from None
            changed = store(payload)
        elif len(args) == 2 and args[0] in ("unlock", "lock", "status"):
            command, job = args[0], validate_job(args[1])
            root = runtime_root()
            if command == "unlock":
                changed = unlock(root, job)
            else:
                directory, _ = cache_directory(root, job)
                if command == "status":
                    print(
                        "unlocked"
                        if all(ready_file(directory / name) for name in CREDENTIALS)
                        else "locked"
                    )
                    return 0
                changed = directory.exists()
                if changed:
                    shutil.rmtree(directory)
        else:
            raise CacheError("Usage: uresticcache store | {unlock,lock,status} JOB")
        print("changed" if changed else "ok")
        return 0
    except CacheError as error:
        print(f"uresticcache: {error}", file=sys.stderr)
    except Exception:
        print("uresticcache: operation failed; check runtime directory access", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
