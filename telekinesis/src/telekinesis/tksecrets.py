"""Secrets for telekinetic operations"""

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Tuple


_op_psynet_cert_item = "psyopsOS_psynet_certificates"
"""The 1Password item for the psynet certificates; must already exist in 1Password

It should have a NODE.crt and a NODE.key field for each node in the psynet.
ca.crt and ca.key are for the certificate authority.
"""


def getsecret(vault: str, item: str, field: str) -> str:
    """Get a secret from 1Password"""
    proc = subprocess.run(
        ["op", "read", f"op://{vault}/{item}/{field}"],
        capture_output=True,
        check=True,
        text=True,
    )
    return proc.stdout.strip()


def psynet_get(host: str) -> Tuple[str, str]:
    """Get a node from the psynet"""
    result = subprocess.run(
        ["op", "item", "get", _op_psynet_cert_item, "--fields", f"{host}.crt,{host}.key"],
        capture_output=True,
        check=True,
    )
    # stdout contains a string like '"<crt>","<key>"'
    # note that the crt and key have quotes around them in the result, so we have to strip that
    # crt and key have newlines in them, but that is ok
    crt, key = result.stdout.decode().split(",")
    return (crt.strip().strip('"'), key.strip().strip('"'))


def psynet_set(host: str, crt: str | Path, key: str | Path) -> None:
    """Set a node's cert and key for psynet (will overwrite if already exists)"""
    if isinstance(crt, Path):
        crt = crt.read_text()
    if isinstance(key, Path):
        key = key.read_text()
    subprocess.run(
        ["op", "item", "edit", _op_psynet_cert_item, f"{host}.crt[password]={crt}"],
        check=True,
    )
    subprocess.run(
        ["op", "item", "edit", _op_psynet_cert_item, f"{host}.key[password]={key}"],
        check=True,
    )


def psynet_delete(host: str) -> None:
    """Delete a node's cert and key for psynet"""
    subprocess.run(
        ["op", "item", "edit", _op_psynet_cert_item, f"{host}.crt[delete]"],
        check=True,
    )
    subprocess.run(
        ["op", "item", "edit", _op_psynet_cert_item, f"{host}.key[delete]"],
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
        crt, key = psynet_get("ca")
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
