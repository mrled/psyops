"""Create a new node in the progfiguration site.

This is not part of the progfiguration API,
just a convenient place to put a script that will only ever run on the controller.

This script isn't available when running from a zipapp.
"""


import argparse
from pathlib import Path
import shutil
import sys
import tempfile
import textwrap
from typing import List, Tuple

from progfiguration import logger
from progfiguration.cli.util import idb_excepthook
from progfiguration.cmd import magicrun
from progfiguration.temple import Temple

import progfiguration_blacksite
import progfiguration_blacksite.sitelib.buildsite


def CommaSeparatedStrList(cssl: str) -> List[str]:
    """Convert a string with commas into a list of strings

    Useful as a type= argument to argparse.add_argument()
    """
    return cssl.split(",")


def CIDRv4(s: str) -> str:
    """Validate an IPv4 CIDR string"""
    try:
        ip_s, mask_s = s.split("/")
        ip = ip_s.split(".")
        if len(ip) != 4:
            raise ValueError("IP address must have 4 parts")
        for part in ip:
            if not 0 <= int(part) <= 255:
                raise ValueError("IP address part must be between 0 and 255")
        mask = int(mask_s)
        if not 0 <= mask <= 32:
            raise ValueError("Mask must be between 0 and 32")
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid CIDR string {s}: {e}") from None
    return s


def gopass_insert(name: str, path: Path) -> None:
    """Insert a secret into gopass"""
    magicrun(["gopass", "insert", "-m", name, "--force", path.as_posix()])


node_py_temple = Temple(
    """\
from progfiguration.inventory.nodes import InventoryNode
from progfiguration.progfigtypes import Bunch

node = InventoryNode(
    address="{$}hostname",
    user="root",
    notes="",
    flavortext="{$}flavor_text",
    age_pubkey="{$}age_pubkey",
    ssh_host_fingerprint="{$}ssh_host_fingerprint",
    psy0mac="{$}psy0mac",
    serial="{$}serial",
    roles=Bunch(),
)
"""
)


node_installer_script_temple = Temple(
    r"""#!/usr/bin/env python3
'''Install the {$}nodename node's configuration'''
from argparse import ArgumentParser
from subprocess import run
from os import makedirs

files = {}
files"nodename" = '''{$}nodename
'''
files["age.key"] = '''{$}age_key
'''
files["mactab"] = '''{$}mactab
'''
files["network.interfaces"] = '''{$}network_interfaces
'''
files["psynet.host.key"] = '''{$}nebula_key
'''
files["psynet.host.crt"] = '''{$}nebula_crt
'''
files["ssh_host_key"] = '''{$}ssh_host_key
'''

parser = ArgumentParser(description=__doc__)
parser.add_argument("device", help="The device to install to, e.g. /dev/sdb. No need for partitions.")
parser.add_argument("--yes-really-delete-all-data-on-device", action="store_true", help="You must pass this flag to confirm that you want to delete all data on the device. This is a safety measure to prevent you from accidentally wiping your disk.")
parser.add_argument("--mount-path", default="/mnt/psyops-secret/mount", help="The path to mount the device to. You should not have to change this from the default of %(default)s unless debugging.")
parsed = parser.parse_args()

if not parsed.yes_really_delete_all_data_on_device:
    parser.error("You must pass --yes-really-delete-all-data-on-device to confirm that you want to delete all data on the device. This is a safety measure to prevent you from accidentally wiping your disk.")
run(["mkfs.ext4", "-L", "psyops-secret", parsed.device], check=True)
makedirs(parsed.mount_path, exist_ok=True)
run(["mount", parsed.device, parsed.mount_path], check=True)

for filename, contents in files.items():
    with open(parsed.mount_path + "/" + filename, "w") as f:
        f.write(contents)
"""
)


def main():
    """Make a new node for the site"""

    parser = argparse.ArgumentParser(
        description="Make a new node for the site",
        epilog=" ".join(
            [
                "This script is not part of the progfiguration API,",
                "just a convenient place to put a script that will only ever run on the controller.",
                "This script must be run from our build environment,",
                "which is the psyops container with decrypted secrets.",
            ]
        ),
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Open the debugger if an unhandled exception is encountered.",
    )
    parser.add_argument(
        "--pyproject-root",
        type=Path,
        default=Path(progfiguration_blacksite.__file__).parent.parent,
        help="Path to the root of the pyproject.toml file. Defaults to %(default)s. You won't need to override this if running from an editable install of a git checkout.",
    )
    parser.add_argument("--clean", action="store_true", help="Clean before building.")

    parser.add_argument("nodename", help="The name you want to use for this node")

    default_hostname = "{nodename}.example.com"
    parser.add_argument(
        "--hostname",
        default=default_hostname,
        help="The hostname to use for this node. Defaults to {default_hostname.format(nodename='NODENAME')}",
    )

    parser.add_argument("--flavor-text", default="", help="Flavor text for the node")

    parser.add_argument(
        "--psynetip",
        type=CIDRv4,
        required=True,
        help="The IP address to use for this node on psynet, in a format like 42.0.66.6/69. Add this address to `ansible/cloudformation/PsynetZone.cfn.yml` and deploy it. Make sure this is unique!",
    )

    psynet_groups_default = "psyopsOS"
    parser.add_argument(
        "--psynet-groups",
        type=CommaSeparatedStrList,
        default=CommaSeparatedStrList(psynet_groups_default),
        help="The groups to add this node to, comma separated. Defaults to %(default)s",
    )

    out_group = parser.add_mutually_exclusive_group()
    outdir_default = "./progfiguration-blacksite-{nodename}-secrets"
    out_group.add_argument(
        "--outdir",
        type=Path,
        help=f"A directory to write the node configuration files to. These files can be written directly to a psyopsOS secrets volume. Defaults to {outdir_default.format(nodename='NODENAME')}",
    )
    out_group.add_argument(
        "--outscript",
        type=Path,
        help="A path to write the installer script to. If this is provided, write a Python script that contains the node configuration files and an installer script. The script will take an argument to a device to install to, e.g. /dev/sdb, and overwrite everything on that device -- :) BE CAREFUL (:",
    )

    parser.add_argument(
        "--nebula-ca-directory",
        type=Path,
        default=Path("/secrets/psyops-secrets/psynet"),
        help="The directory containing the nebula CA, see ./psynet.md for more information. Defaults to %(default)s",
    )

    parser.add_argument(
        "--mac-address",
        default="00:00:00:00:00:00",
        help="The MAC address of the node's NIC card. If this is not provided it defaults to %(default)s, and you must edit the resulting mactab file with the real address or the network will not be configured properly.",
    )

    parser.add_argument(
        "--serial",
        default="00000000",
        help="The serial number or service tag for the hardeware. Defaults to all %(default)s.",
    )

    parsed = parser.parse_args()

    logger.setLevel("DEBUG")

    if parsed.debug:
        sys.excepthook = idb_excepthook

    if not (parsed.pyproject_root / "pyproject.toml").exists():
        raise RuntimeError(
            f"pyproject.toml not found at {parsed.pyproject_root}, please specify the path to the root of the pyproject.toml file with the --pyproject-root option. Note that you should generally be running this script from an editable install of a git checkout, where this will not be necessary."
        )

    # outdir = parsed.outdir
    # if not outdir:
    #     outdir = Path(outdir_default.format(nodename=parsed.nodename))

    with tempfile.TemporaryDirectory() as tmpdir:

        (tmpdir / "nodename").open("w").write(parsed.nodename)

        age_keygen_result = magicrun(["age-keygen", "-o", tmpdir / "age.key"])
        age_pubkey = age_keygen_result.stdout.decode("utf-8").strip().split(" ")[2]
        # gopass_insert(f"psyopsOS/{parsed.nodename}.age.key", outdir / "age.key")

        magicrun(
            [
                "ssh-keygen",
                "-q",
                "-f",
                tmpdir / "ssh_host_ed25519_key",
                "-N",
                "",
                "-t",
                "ed25519",
            ]
        )
        with (tmpdir / "ssh_host_ed25519_key.pub").open("r") as f:
            ssh_host_fingerprint = f.read()
        # No need to keep this around, we regenerate it on boot
        (tmpdir / "ssh_host_ed25519_key").unlink()

        magicrun(
            [
                "nebula-cert",
                "sign",
                "-name",
                parsed.nodename,
                "-ip",
                parsed.psynetip,
                "-groups",
                ",".join(parsed.psynet_groups),
            ],
            cwd=parsed.nebula_ca_directory,
        )
        nebula_key = parsed.nebula_ca_directory / f"{parsed.nodename}.key"
        nebula_crt = parsed.nebula_ca_directory / f"{parsed.nodename}.crt"

        shutil.move(nebula_key, tmpdir / "psynet.host.key")
        shutil.move(nebula_crt, tmpdir / "psynet.host.crt")
        gopass_insert(f"psynet/{parsed.nodename}.key", nebula_key)
        gopass_insert(f"psynet/{parsed.nodename}.crt", nebula_crt)

        (tmpdir / "mactab").open("r").write(f"psy0 {parsed.mac_address}\n")

        with (tmpdir / "network.interfaces").open("w") as f:
            f.write(
                textwrap.dedent(
                    """\
                    auto lo
                    iface lo inet loopback

                    auto psy0
                    iface psy0 inet dhcp
                    """
                )
            )

    node_py_file = (
        Path(progfiguration_blacksite.nodes.__file__).parent / f"{parsed.nodename}.py"
    )
    if node_py_file.exists():
        raise RuntimeError(
            f"Node file {node_py_file} already exists, please delete it first"
        )
    node_py_file.open("w").write(
        node_py_temple.substitute(
            hostname=parsed.hostname,
            flavor_text=parsed.flavor_text,
            age_pubkey=age_pubkey,
            ssh_host_fingerprint=ssh_host_fingerprint,
            psy0mac=parsed.mac_address,
            serial=parsed.serial,
        )
    )

    # TODO: Either handle minisign pubkey in this script, or remove minisign from the design.
    # I've never used it, but have thought it would be useful to be able to prove that somethins is signed by the controller without having to encrypt it separately for each node.
