"""SSH operations"""


import os
from pathlib import Path
import subprocess
import tempfile

from progfiguration.cmd import run
from progfiguration.progfigtypes import AnyPathOrStr


def _generate_pubkey_from_path(path: Path) -> str:
    """Generate a public key from a private key"""
    return run(["ssh-keygen", "-y", "-f", str(path)], print_output=False).stdout.read()


def _generate_pubkey_from_string(key: str) -> str:
    """Generate a public key from a private key"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        key_path = tmpdir / "key"
        key_path.write_text(key)
        key_path.chmod(0o600)
        return _generate_pubkey_from_path(key_path)


def generate_pubkey(privkey: AnyPathOrStr) -> str:
    """Generate a public key from a private key"""
    if isinstance(privkey, str):
        if os.path.exists(privkey):
            return _generate_pubkey_from_path(Path(privkey))
        else:
            return _generate_pubkey_from_string(privkey)
    else:
        return _generate_pubkey_from_path(privkey)
