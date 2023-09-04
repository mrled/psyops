#!/usr/bin/env python3

"""Update Synology TLS certificates

Written for DSM 7.

References:

* <https://gist.github.com/catchdave/69854624a21ac75194706ec20ca61327>
"""

import argparse
import glob
import logging
import os
import pdb
import shutil
import subprocess
import sys
import tempfile
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


def install_tls(key_tmp, cert_tmp):
    """Install the TLS certificates

    The arguments are paths to temporary files containing the key and the cert.
    They will be moved from these locations!

    Note that we rely on the lego behavior of the certificate actually being
    the fullchain.pem, and the issuer being in a separate file (which we ignore).
    So we just copy use the cert as both cert and fullchain.
    """

    certs_src_dir = "/usr/syno/etc/certificate/system/default"
    key = os.path.join(certs_src_dir, "privkey.pem")
    crt = os.path.join(certs_src_dir, "cert.pem")
    chain = os.path.join(certs_src_dir, "fullchain.pem")

    shutil.move(key_tmp, key)
    shutil.move(cert_tmp, crt)
    shutil.copyfile(crt, chain)

    services_to_restart = ["nmbd", "avahi", "ldap-server"]
    packages_to_restart = ["ScsiTarget", "SynologyDrive", "WebDAVServer", "ActiveBackup"]

    # All the target directories I know about
    # Sometimes these don't exist, maybe because the app is not installed
    target_cert_dirs = [
        "/usr/syno/etc/certificate/system/FQDN",
        "/usr/local/etc/certificate/ScsiTarget/pkg-scsi-plugin-server/",
        "/usr/local/etc/certificate/SynologyDrive/SynologyDrive/",
        "/usr/local/etc/certificate/WebDAVServer/webdav/",
        "/usr/local/etc/certificate/ActiveBackup/ActiveBackup/",
        "/usr/syno/etc/certificate/smbftpd/ftpd/",
    ]

    # The DEFAULT directory
    # This is some weird Synology thing
    # <https://www.reddit.com/r/synology/comments/8oqdxv/where_are_stored_ssl_certificates_lets_encrypt_on/>
    default_dir_file = "/usr/syno/etc/certificate/_archive/DEFAULT"
    with open(default_dir_file, "r") as file:
        default_dir_name = file.readline().strip()
        if not default_dir_name:
            raise Exception(f"Default directory name not found in {default_dir_file}")
        target_cert_dirs.append(f"/usr/syno/etc/certificate/_archive/{default_dir_name}")

    # Add reverse proxy app directories
    proxy_dirs = glob.glob("/usr/syno/etc/certificate/ReverseProxy/*/")
    target_cert_dirs.extend(proxy_dirs)

    # Check target directories
    for target_dir in target_cert_dirs:
        if not os.path.isdir(target_dir):
            logging.warning(f"Target cert directory '{target_dir}' not found, skipping...")
            continue
        logging.info(f"Installing TLS certificates in {target_dir}")
        install(key, os.path.join(target_dir, "privkey.pem"), 0, 0, 0o600)
        install(crt, os.path.join(target_dir, "cert.pem"), 0, 0, 0o644)
        install(chain, os.path.join(target_dir, "fullchain.pem"), 0, 0, 0o644)

    # Reload nginx
    subprocess.run(["/usr/syno/bin/synosystemctl", "restart", "nginx"], check=True)

    # Restart services and packages
    for service in services_to_restart:
        is_active = subprocess.run(["/usr/syno/bin/synosystemctl", "get-active-status", service], capture_output=True)
        if is_active.stdout.decode().strip() == "active":
            logger.info(f"Restarting service {service}")
            subprocess.run(["/usr/syno/bin/synosystemctl", "restart", service], check=True)
        else:
            logger.info(f"Service {service} is not active, skipping...")

    for package in packages_to_restart:
        is_onoff = subprocess.run(
            ["/usr/syno/bin/synopkg", "is_onoff", package], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        previously_on = is_onoff.returncode == 0
        if previously_on:
            logger.info(f"Restarting package {package}")
            subprocess.run(["/usr/syno/bin/synopkg", "restart", package], check=True)
        else:
            logger.info(f"Package {package} is not on, skipping...")


def main(*arguments):

    parser = argparse.ArgumentParser(description="Install Synology TLS certificates")

    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Launch a debugger on unhandled exception",
    )
    parser.add_argument("key", help="Path to key file")
    parser.add_argument("cert", help="Path to certificate file")

    parsed = parser.parse_args(arguments[1:])

    if not os.path.exists(parsed.key):
        raise Exception("No key at {}".format(parsed.key))
    if not os.path.exists(parsed.cert):
        raise Exception("No certificate at {}".format(parsed.cert))

    if parsed.debug:
        sys.excepthook = idb_excepthook

    install_tls(parsed.key, parsed.cert)


if __name__ == "__main__":
    sys.exit(main(*sys.argv))
