#!/usr/bin/env python3

"""Save ed25519 keys in the format required by tor.

Thanks to genuineDeveloperBrain, <https://tor.stackexchange.com/a/23674>
"""

import argparse
import base64
import hashlib
import os
import pdb
import pwd
import sys
import traceback
from pathlib import Path
from typing import Union


def idb_excepthook(type, value, tb):
    """Call an interactive debugger in post-mortem mode

    If you do "sys.excepthook = idb_excepthook", then an interactive debugger
    will be spawned at an unhandled exception
    """
    if hasattr(sys, "ps1") or not sys.stderr.isatty():
        sys.__excepthook__(type, value, tb)
    else:
        traceback.print_exception(type, value, tb)
        print
        pdb.pm()


def expand_private_key(secret_key) -> bytes:
    hash = hashlib.sha512(secret_key[:32]).digest()
    hash = bytearray(hash)
    hash[0] &= 248
    hash[31] &= 127
    hash[31] |= 64
    return bytes(hash)


def onion_address_from_public_key(public_key: bytes) -> str:
    version = b"\x03"
    checksum = hashlib.sha3_256(b".onion checksum" + public_key + version).digest()[:2]
    onion_address = "{}.onion".format(base64.b32encode(public_key + checksum + version).decode().lower())
    return onion_address


def verify_v3_onion_address(onion_address: str) -> list[bytes, bytes, bytes]:
    # v3 spec https://gitweb.torproject.org/torspec.git/plain/rend-spec-v3.txt
    try:
        decoded = base64.b32decode(onion_address.replace(".onion", "").upper())
        public_key = decoded[:32]
        checksum = decoded[32:34]
        version = decoded[34:]
        if checksum != hashlib.sha3_256(b".onion checksum" + public_key + version).digest()[:2]:
            raise ValueError
        return public_key, checksum, version
    except:
        raise ValueError("Invalid v3 onion address")


def create_hs_ed25519_secret_key_content(signing_key: bytes) -> bytes:
    return b"== ed25519v1-secret: type0 ==\x00\x00\x00" + expand_private_key(signing_key)


def create_hs_ed25519_public_key_content(public_key: bytes) -> bytes:
    assert len(public_key) == 32
    return b"== ed25519v1-public: type0 ==\x00\x00\x00" + public_key


def store_bytes_to_file(bytes: bytes, filename: str, uid: int = None, gid: int = None) -> str:
    with open(filename, "wb") as binary_file:
        binary_file.write(bytes)
    if uid and gid:
        os.chown(filename, uid, gid)
    return filename


def store_string_to_file(string: str, filename: str, uid: int = None, gid: int = None) -> str:
    with open(filename, "w") as file:
        file.write(string)
    if uid and gid:
        os.chown(filename, uid, gid)
    return filename


def create_hidden_service_files(
    private_seed: bytes,
    public_key: bytes,
    hidden_service_dir: Union[str, Path],
    tor_username: str,
    overwrite: bool = False,
) -> None:

    if not isinstance(hidden_service_dir, Path):
        hidden_service_dir = Path(hidden_service_dir)

    # these are not strictly needed but takes care of the file permissions need by tor
    user = pwd.getpwnam(tor_username)
    uid = user.pw_uid
    gid = user.pw_gid

    if hidden_service_dir.exists():
        if overwrite:
            print(f"Overwriting any existing files in {str(hidden_service_dir)}")
        else:
            raise FileExistsError(f"{str(hidden_service_dir)} already exists.")
    else:
        os.mkdir(str(hidden_service_dir))
        os.chmod(str(hidden_service_dir), 0o700)
        os.chown(str(hidden_service_dir), uid, gid)

    file_content_secret = create_hs_ed25519_secret_key_content(private_seed)

    store_bytes_to_file(file_content_secret, f"{str(hidden_service_dir)}/hs_ed25519_secret_key", uid, gid)

    file_content_public = create_hs_ed25519_public_key_content(public_key)
    store_bytes_to_file(file_content_public, f"{str(hidden_service_dir)}/hs_ed25519_public_key", uid, gid)

    onion_address = onion_address_from_public_key(public_key)
    store_string_to_file(onion_address, f"{str(hidden_service_dir)}/hostname", uid, gid)

    return onion_address


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a hidden service from existing key")
    parser.add_argument("--debug", "-d", action="store_true", help="debug")
    parser.add_argument(
        "--private-key", help="32 bytes private key in hex. If not passed, one is generated (requires pynacl)."
    )
    parser.add_argument(
        "--public-key",
        help="32 bytes public key in hex. If not passed, it's generated from the private key (requires pynacl).",
    )
    parser.add_argument("--tor-user", default="tor", help="Name of tor user")
    parser.add_argument("--force", "-f", action="store_true", help="Force overwrite of existing files")
    parser.add_argument("hidden_service_dir", help="tor hidden service directory")
    parsed = parser.parse_args()

    if parsed.debug:
        sys.excepthook = idb_excepthook

    if not parsed.private_key or not parsed.public_key:
        # Leave imports to runtime so that we can use the important functions in the script without pynacl
        try:
            import nacl.bindings
            import nacl.signing
        except ImportError:
            print("pynacl is required to generate a private and/or public key")
            sys.exit(1)
    if parsed.public_key and not parsed.private_key:
        parser.error("public key requires private key")

    if parsed.private_key:
        private_key_seed = bytes.fromhex(parsed.private_key)
    else:
        privkey = nacl.signing.SigningKey.generate()
        private_key_seed = privkey._seed

    if parsed.public_key:
        public_key = bytes.fromhex(parsed.public_key)
    else:
        public_key, secret_key = nacl.bindings.crypto_sign_seed_keypair(private_key_seed)

    onion_address = create_hidden_service_files(
        private_key_seed,
        public_key,
        parsed.hidden_service_dir,
        parsed.tor_user,
        parsed.force,
    )

    print(f"Created hidden service with address {onion_address}")
