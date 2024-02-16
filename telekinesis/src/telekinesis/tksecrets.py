"""Secrets for telekinetic operations

This expects a working gopass installation
with the psyops password store already mounted to the 'psyops' alias.
"""

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path


def gopass_get(path: str, mount: str = "psyops/") -> str:
    """Get a secret from psyops

    gopass is not supposed to add a newline to the end of the secret unless its being printed to the terminal.
    <https://github.com/gopasspw/gopass/pull/325>
    However, it seems that this isn't working.
    Going to strip exactly one newline from the end of the output to work around this,
    but if gopass fixes it, my fix will break everything.

    What they need is a way to tell it explicitly to not add a newline.
    """
    fullpath = f"{mount}{path}"
    proc = subprocess.run(
        ["gopass", "cat", fullpath],
        capture_output=True,
        check=True,
        text=True,
    )
    result = proc.stdout[0:-1]
    return result


def gopass_set(value: str | Path, path: str, mount: str = "psyops/") -> None:
    """Set a secret in psyops"""
    if isinstance(value, Path):
        value = value.read_text()
    fullpath = f"{mount}{path}"
    subprocess.run(
        ["gopass", "insert", "-f", fullpath],
        input=value,
        check=True,
        text=True,
    )


def gopass_rm(path: str, mount: str = "psyops/") -> None:
    """Remove a secret from psyops"""
    fullpath = f"{mount}{path}"
    subprocess.run(
        ["gopass", "rm", fullpath],
        check=True,
    )


@contextmanager
def psynetca(directory: Path | None = None):
    """A context manager that yields a directory containing the psynet CA

    If directory is None, a temporary directory is created and yielded.
    Otherwise, the passed directory is yielded,
    the crt/key are written to it,
    and the crt/key are deleted when the context manager exits.
    """
    tempdir = None
    try:
        if directory is None:
            tempdir = Path(tempfile.mkdtemp())
            directory = tempdir
        crtpath = directory / "ca.crt"
        keypath = directory / "ca.key"
        crt = gopass_get("psynet/ca.crt")
        key = gopass_get("psynet/ca.key")
        with open(crtpath, "w") as f:
            f.write(crt)
        with open(keypath, "w") as f:
            f.write(key)
        yield directory
    finally:
        crtpath.unlink()
        keypath.unlink()
        if tempdir is not None:
            shutil.rmtree(tempdir)
