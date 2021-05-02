#!/usr/bin/python3


import subprocess
import typing


def wireguard_public_key(privkey: typing.Union[str, bytes]) -> str:
    """Given a wireguard private key, return the public key.

    Note that the 'wg' command must be installed.
    """

    # Make sure our input is a str
    try:
        privkey_stdin: str = privkey.decode()
    except AttributeError:
        privkey_stdin: str = privkey

    # The normal command-line generation process:
    # wg genkey | tee privatekey | wg pubkey > publickey

    wg = subprocess.Popen(
        ["wg", "pubkey"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    wgout, wgerr = wg.communicate(privkey_stdin)
    wg.wait()

    if wg.returncode != 0:
        raise subprocess.CalledProcessError(
            wg.returncode, wg.cmd, output=wgout, stderr=wgerr
        )

    return wgout.strip()


class FilterModule(object):
    def filters(self):
        return {
            "wireguard_public_key": wireguard_public_key,
        }
