#!/usr/bin/env python

"""Update Synology TLS certificates

This must work under Python 2, as Synology does not ship Python 3.
"""

import argparse
import logging
import os
import pdb
import shutil
import subprocess
import sys
import traceback


logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)


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


def install(src, dst, owner, group, mode):
    """Install a file, specifying owner, group, and mode"""
    shutil.copy(src, dst)
    os.chown(dst, owner, group)
    os.chmod(dst, mode)


def install_tls_synoweb(crt, key, baksfx="syno-tls-update-backup"):
    """Install certificates to the main webserver

    This webserver runs the Synology admin UI, and also Syncthing if it is
    installed, among other things.

    crt     Path to the certificate with full chain
    key     Path to the private key
    baksfx  The backup suffix for the certificate dir
            If there is not already a certificate directory with this suffix,
            copy the actual certificate directory to it.
    """
    certdir = "/usr/syno/etc/certificate"
    backupdir = "{}.{}".format(certdir, baksfx)

    if not os.path.exists(backupdir):
        logger.info("Backing up certdir from {} to {}".format(certdir, backupdir))
        shutil.copytree(certdir, backupdir)
    else:
        logger.info("No need to back up, dir already exists at {}".format(backupdir))

    logger.info("Installing certificate...")
    install(crt, "{}/system/default/fullchain.pem".format(certdir), 0, 0, 0o600)
    logger.info("Installing key...")
    install(key, "{}/system/default/privkey.pem".format(certdir), 0, 0, 0o600)

    logger.info("Reloading webserver...")
    subprocess.call(["/usr/syno/sbin/synoservice", "--reload", "nginx"])


def install_tls_webdav(crt, key, baksfx="syno-tls-update-backup"):
    """Install certificates to the WebDAV webserver

    The WebDAV Synology package must be installed for this to work.

    crt     Path to the certificate with full chain
    key     Path to the private key
    baksfx  The backup suffix for the certificate dir
            If there is not already a certificate directory with this suffix,
            copy the actual certificate directory to it.
    """
    certdir = "/usr/local/etc/certificate/WebDAVServer/webdav"
    backupdir = "{}.{}".format(certdir, baksfx)

    if not os.path.exists(backupdir):
        logger.info("Backing up certdir from {} to {}".format(certdir, backupdir))
        shutil.copytree(certdir, backupdir)
    else:
        logger.info("No need to back up, dir already exists at {}".format(backupdir))

    # Installing the same to both cert.pem and fullchain.pem,
    # or else httpd won't start, lol
    logger.info("Installing certificate...")
    install(crt, "{}/fullchain.pem".format(certdir), 0, 0, 0o600)
    install(crt, "{}/cert.pem".format(certdir), 0, 0, 0o600)
    logger.info("Installing key...")
    install(key, "{}/privkey.pem".format(certdir), 0, 0, 0o600)

    logger.info("Reloading WebDAV server...")
    subprocess.call(["/usr/syno/sbin/synoservice", "--restart", "pkgctl-WebDAVServer"])


def parseargs(arguments):
    """Parse program arguments"""

    parser = argparse.ArgumentParser(description="Install Synology TLS certificates")

    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Launch a debugger on unhandled exception",
    )

    valid_modes = ["synoweb", "webdav"]
    parser.add_argument(
        "mode",
        help="One or more modes, comma separated. Valid modes: {}".format(valid_modes),
    )
    parser.add_argument("cert", help="Path to the certificate, including full cert chain")
    parser.add_argument("key", help="Path to the private key")
    parsed = parser.parse_args(arguments)

    parsed.mode = parsed.mode.split(",")
    for mode in parsed.mode:
        if mode not in valid_modes:
            raise Exception("Invalid mode {}".format(mode))
    if not os.path.exists(parsed.cert):
        raise Exception("No certificate at {}".format(parsed.cert))
    if not os.path.exists(parsed.key):
        raise Exception("No key at {}".format(parsed.key))

    return parsed


def main(*arguments):
    """Main program"""
    parsed = parseargs(arguments[1:])

    if parsed.debug:
        sys.excepthook = idb_excepthook

    if "synoweb" in parsed.mode:
        install_tls_synoweb(parsed.cert, parsed.key)
    if "webdav" in parsed.mode:
        install_tls_webdav(parsed.cert, parsed.key)


if __name__ == "__main__":
    sys.exit(main(*sys.argv))
