#!/usr/bin/python3


import argparse
import base64
import binascii
import hashlib
import os
import pdb
import sys
import traceback
from typing import AnyStr, NamedTuple


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


def anystr2utf8bytes(a: AnyStr) -> bytes:
    if not isinstance(a, bytes):
        return bytes(a, "utf-8")
    return a


class AdaptableBytes(NamedTuple):
    """Store bytes onces, easily get str/base64.

    Input bytes can be anything, but when stringified are assumed to be utf-8.
    """

    b: bytes

    @property
    def s(self) -> str:
        return self.b.decode("utf-8")

    @property
    def b64(self) -> str:
        return base64.b64encode(self.b).decode("utf-8")


class SaltedPassword(NamedTuple):
    """A hashed password and its salt

    (Does not contain password plaintext.)
    """

    password: AdaptableBytes
    salt: AdaptableBytes

    @classmethod
    def from_anystr(cls, password: AnyStr, salt: AnyStr) -> "SaltedPassword":
        password = anystr2utf8bytes(password)
        salt = anystr2utf8bytes(salt)
        return cls(AdaptableBytes(password), AdaptableBytes(salt))

    @property
    def ssha_suffixed(self) -> str:
        """An SSHA password with the salt suffixed.

        If the input is SHA1, this is suitable for the LDAP Account Manager 'password:' setting in its config file.
        """
        result = "{SSHA}%s %s" % (self.password.b64, self.salt.b64)
        return result


def random_salt(size: int = 64) -> bytes:
    return os.urandom(size)


def ssha_sha1_suffixed(password: bytes, salt: bytes = None):
    """Generate a SSHA password based on sha1 with the salt suffixed."""
    salt = salt or random_salt()
    hash = hashlib.sha1(password + salt)
    salted_hash = SaltedPassword.from_anystr(hash.digest(), salt)
    return salted_hash.ssha_suffixed


def main():
    """A main function for command-line testing

    The password found here in the lam configuration:
    <https://geek-cookbook.funkypenguin.co.nz/recipes/openldap/>
    is this:
        password: {SSHA}D6AaX93kPmck9wAxNlq3GF93S7A= R7gkjQ==

    You can generate that with this command with:
        python3 filter_plugins/ssha.py lam --salt 47b8248d
    """
    parser = argparse.ArgumentParser(description="SSHA related stuff")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enter the debugger on an unhandled exception",
    )
    parser.add_argument("password", help="Password (plaintext)")
    parser.add_argument(
        "--salt",
        help="A salt in hex digits, where e.g. a salt of ASCII 'abcd' would be '61626364'",
    )
    parsed = parser.parse_args()

    if parsed.debug:
        sys.excepthook = idb_excepthook

    if parsed.salt:
        salt = binascii.unhexlify(parsed.salt)
    else:
        salt = None

    password = anystr2utf8bytes(parsed.password)

    result = ssha_sha1_suffixed(password, salt)
    print(result)


class FilterModule(object):
    def filters(self):
        return {
            "ssha_sha1_suffixed": ssha_sha1_suffixed,
        }


if __name__ == "__main__":
    main()
