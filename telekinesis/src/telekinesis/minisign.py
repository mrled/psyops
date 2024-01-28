"""Minisign signing and verification."""


import subprocess
from typing import Union

from telekinesis.config import getsecret, tkconfig


def sign(files: Union[str, list[str]], trusted_comment: str = "", untrusted_comment: str = "") -> None:
    """Sign files with minisign."""
    if isinstance(files, str):
        files = [files]
    mspassword = getsecret("Personal", "psyopsOS-minisign.seckey", "password")
    cmd = ["minisign", "-S", "-s", tkconfig.repopaths.minisign_seckey]
    if trusted_comment:
        cmd += ["-t", trusted_comment]
    if untrusted_comment:
        cmd += ["-c", untrusted_comment]
    cmd += ["-m", *files]
    result = subprocess.run(cmd, check=True, text=True, input=mspassword)


def verify(file: str) -> None:
    """Verify a file with minisign."""
    result = subprocess.run(
        ["minisign", "-V", "-p", tkconfig.repopaths.minisign_pubkey, "-m", file],
        check=True,
        text=True,
    )
    print(result.stdout)
