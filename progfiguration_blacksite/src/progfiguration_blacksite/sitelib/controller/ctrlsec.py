"""Controller secrets management"""


import subprocess
from pathlib import Path
from typing import Tuple


_op_psynet_cert_item = "psyopsOS_psynet_certificates"
"""The 1Password item for the psynet certificates; must already exist in 1Password

It should have a NODE.crt and a NODE.key field for each node in the psynet.
ca.crt and ca.key are for the certificate authority.
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
    return (crt.strip('"'), key.strip('"'))


def psynet_set(host: str, crt: str | Path, key: str | Path) -> None:
    """Set a node's cert and key for psynet (will overwrite if already exists)"""
    if isinstance(crt, Path):
        crt = crt.read_text()
    if isinstance(key, Path):
        key = key.read_text()
    subprocess.run(
        ["op", "item", "edit", _op_psynet_cert_item, f"{host}.crt[password]={crt}" f"{host}.key[password]={key}"],
        check=True,
    )
