"""Controller secrets management"""


from contextlib import contextmanager
import shutil
import subprocess
from pathlib import Path
import tempfile
from typing import Tuple


_op_psynet_cert_item = "psyopsOS_psynet_certificates"
"""The 1Password item for the psynet certificates; must already exist in 1Password

It should have a NODE.crt and a NODE.key field for each node in the psynet.
ca.crt and ca.key are for the certificate authority.
"""

_op_age_keys_item = "psyopsOS_age_keys"
"""The 1Password item for the age keys; must already exist in 1Password

It should have a NODE.age field for all psyopsOS nodes.
"""

_op_sshhost_keys_item = "psyopsOS_sshhost_keys"
"""The 1Password item for the ssh host keys; must already exist in 1Password

It should have a NODE field for all psyopsOS nodes.
"""


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
def psynetca():
    """A context manager that yields a temporary directory containing the psynet CA"""
    try:
        temp_dir = Path(tempfile.mkdtemp())
        crt, key = psynet_get("ca")
        with open(temp_dir / "ca.crt", "w") as f:
            f.write(crt)
        with open(temp_dir / "ca.key", "w") as f:
            f.write(key)
        yield temp_dir
    finally:
        # import pdb

        # pdb.set_trace()
        shutil.rmtree(temp_dir)


def age_get(host: str) -> str:
    """Get an age key from 1Password"""
    result = subprocess.run(
        ["op", "item", "get", _op_age_keys_item, "--fields", f"{host}.age"],
        capture_output=True,
        check=True,
    )
    return result.stdout.decode().strip().strip('"')


def age_set(host: str, key: str | Path) -> None:
    """Set an age key for a node (will overwrite if already exists)"""
    if isinstance(key, Path):
        key = key.read_text()
    subprocess.run(
        ["op", "item", "edit", _op_age_keys_item, f"{host}.age[password]={key}"],
        check=True,
    )


def age_delete(host: str) -> None:
    """Delete an age key for a node"""
    subprocess.run(
        ["op", "item", "edit", _op_age_keys_item, f"{host}.age[delete]"],
        check=True,
    )


def sshhost_get(host: str) -> str:
    """Get an ssh host key from 1Password"""
    result = subprocess.run(
        ["op", "item", "get", _op_sshhost_keys_item, "--fields", f"{host}.age"],
        capture_output=True,
        check=True,
    )
    return result.stdout.decode().strip().strip('"')


def sshhost_set(host: str, key: str | Path) -> None:
    """Set an ssh host key for a node (will overwrite if already exists)"""
    if isinstance(key, Path):
        key = key.read_text()
    subprocess.run(
        ["op", "item", "edit", _op_sshhost_keys_item, f"{host}.age[password]={key}"],
        check=True,
    )


def sshhost_delete(host: str) -> None:
    """Delete an ssh host key for a node"""
    subprocess.run(
        ["op", "item", "edit", _op_sshhost_keys_item, f"{host}[delete]"],
        check=True,
    )
