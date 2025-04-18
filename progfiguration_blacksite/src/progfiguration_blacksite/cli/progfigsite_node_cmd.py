"""Create a new node in the progfiguration site.

This is not part of the progfiguration API,
just a convenient place to put a script that will only ever run on the controller.

This script isn't available when running from a zipapp.

TODO: migrate this to telekinesis, and remove duplicated code like the psynetca context manager.
"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import textwrap

from progfiguration import logger, sitewrapper
from progfiguration.cli.util import idb_excepthook
from progfiguration.cmd import magicrun

import progfiguration_blacksite
from progfiguration_blacksite.sitelib.controller import nodemgmt

from telekinesis import tksecrets


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


def check_node_exists(nodename: str) -> bool:
    """Check if a node exists"""
    try:
        sitewrapper.site_submodule(f"nodes.{nodename}")
    except ModuleNotFoundError:
        return False
    else:
        return True


class NodeSecrets:
    """Files required for a node secrets mount"""

    _agepub: str
    _sshhostprint: str

    def __init__(self, secroot: Path):
        self.secroot = secroot
        """The root directory for the node secrets"""
        self.nodename = secroot / "nodename"
        """A file called nodename which contains the node's name"""
        self.agekey = secroot / "age.key"
        """The age private key for the node"""
        self.mactab = secroot / "mactab"
        """The mactab file for the node"""
        self.nebulakey = secroot / "psynet.host.key"
        """The nebula private key for the node"""
        self.nebulacrt = secroot / "psynet.host.crt"
        """The nebula certificate for the node"""
        self.sshhostkey = secroot / "ssh_host_ed25519_key"
        """The ssh host key for the node"""
        self.interfaces = secroot / "network.interfaces"
        """The network.interfaces file for the node"""
        self.files = [
            self.nodename,
            self.agekey,
            self.mactab,
            self.nebulakey,
            self.nebulacrt,
            self.sshhostkey,
            self.interfaces,
        ]
        """All files that must be present on a psyops-secret volume"""

    @property
    def agepub(self) -> str:
        if not self._agepub:
            self._agepub = self.agekey.read_text().split(" ")[2]
        return self._agepub

    @property
    def sshhostprint(self) -> str:
        """The SSH host key fingerprint for the node"""
        if not self._sshhostprint:
            subprocess.run(["ssh-keygen", "-y", "-f", self.sshhostkey], capture_output=True, check=True, text=True)
            self._sshhostprint = self.sshhostkey.read_text()
        # The private key must end with a newline
        return self._sshhostprint + "\n"

    def save_directory(self, outdir: Path):
        for f in self.files:
            shutil.move(f, outdir / f.name)

    def save_installer_script(self, outscript: Path):
        outscript.open("w").write(
            nodemgmt.make_node_installer_script_temple(
                nodename=self.nodename.read_text(),
                age_key=self.agekey.read_text(),
                mactab=self.mactab.read_text(),
                nebula_key=self.nebulakey.read_text(),
                nebula_crt=self.nebulacrt.read_text(),
                ssh_host_key=self.sshhostkey.read_text(),
            )
        )

    def write_interfaces(self) -> None:
        """Create a new network.interfaces file"""
        with self.interfaces.open("w") as f:
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

    @classmethod
    def new(
        cls,
        secroot: Path,
        nodename: str,
        psynetip: str,
        psynet_groups: list[str],
        nebula_ca_directory: Path,
        mac_address: str,
    ):
        """Create a new node secrets directory, and make new keys etc."""
        nodefiles = cls(secroot)

        # Simple file creation
        nodefiles.nodename.open("w").write(nodename)
        nodefiles.mactab.open("w").write(f"psy0 {mac_address}\n")
        nodefiles.write_interfaces()

        # Age key generation
        age_keygen_result = magicrun(["age-keygen", "-o", nodefiles.agekey])
        age_keygen_err = age_keygen_result.stderr.read().strip()
        nodefiles._agepub = age_keygen_err.split(" ")[2]
        tksecrets.gopass_set(nodefiles.agekey, f"progfiguration/nodeage/{nodename}.age")

        # SSH key generation
        magicrun(["ssh-keygen", "-q", "-f", nodefiles.sshhostkey, "-N", "", "-t", "ed25519"])
        ssh_host_pubkey = secroot / "ssh_host_ed25519_key.pub"
        with ssh_host_pubkey.open("r") as f:
            # The private key must end with a newline
            nodefiles._sshhostprint = f.read() + "\n"
        # No need to keep this around, we regenerate it on boot
        ssh_host_pubkey.unlink()
        tksecrets.gopass_set(nodefiles.sshhostkey, f"psyopsOS/sshhostkeys/{nodename}")

        # Nebula key generation
        magicrun(
            [
                "nebula-cert",
                "sign",
                "-name",
                nodename,
                "-ip",
                psynetip,
                "-groups",
                ",".join(psynet_groups),
                "-out-key",
                nodefiles.nebulakey,
                "-out-crt",
                nodefiles.nebulacrt,
            ],
            cwd=nebula_ca_directory,
        )
        tksecrets.gopass_set(nodefiles.nebulakey, f"psynet/{nodename}.key")
        tksecrets.gopass_set(nodefiles.nebulacrt, f"psynet/{nodename}.crt")

        # TODO: Either handle minisign pubkey in this script, or remove minisign from the design.
        # I've never used it, but have thought it would be useful to be able to prove that somethins is signed by the controller without having to encrypt it separately for each node.

        return nodefiles

    @classmethod
    def from_existing(cls, secroot: Path, nodename: str):
        """Retrieve node secrets from the secret store, and save them to a directory"""
        nodefiles = cls(secroot)

        # Info from inventory node module
        nodemod = sitewrapper.site_submodule(f"nodes.{nodename}")
        mac_address = nodemod.node.sitedata["psy0mac"]

        # Simple file creation
        nodefiles.nodename.open("w").write(nodename)
        nodefiles.write_interfaces()
        nodefiles.mactab.open("w").write(f"psy0 {mac_address}\n")

        # Age key retrieval
        node_age = tksecrets.gopass_get(f"progfiguration/nodeage/{nodename}.age")
        nodefiles.agekey.open("w").write(node_age)
        nodefiles._agepub = nodemod.node.sitedata["age_pubkey"]

        # SSH key retrieval
        node_ssh = tksecrets.gopass_get(f"psyopsOS/sshhostkeys/{nodename}")
        # The private key must end with a newline
        nodefiles.sshhostkey.open("w").write(node_ssh + "\n")
        nodefiles._sshhostprint = nodemod.node.ssh_host_fingerprint

        # Nebula key retrieval
        nebula_crt = tksecrets.gopass_get(f"psynet/{nodename}.crt")
        nebula_key = tksecrets.gopass_get(f"psynet/{nodename}.key")
        nodefiles.nebulacrt.open("w").write(nebula_crt)
        nodefiles.nebulakey.open("w").write(nebula_key)

        return nodefiles


def makeparser():
    """Return a parser for the progfigsite node command"""

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
        default=Path(progfiguration_blacksite.__file__).parent.parent.parent,
        help="Path to the root of the pyproject.toml file. Defaults to %(default)s. You won't need to override this if running from an editable install of a git checkout.",
    )

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # The out* parent parser
    outparser = argparse.ArgumentParser(add_help=False)
    outgroup = outparser.add_mutually_exclusive_group()
    outdir_default = "./progfiguration-blacksite-{nodename}-secrets"
    outgroup.add_argument(
        "--outdir",
        default="./progfiguration-blacksite-{nodename}-secrets",
        help=f"A directory to write the node configuration files to. These files can be written directly to a psyopsOS secrets volume. Defaults to {outdir_default.format(nodename='NODENAME')}",
    )
    outgroup.add_argument(
        "--outscript",
        type=Path,
        help="A path to write the installer script to. If this is provided, write a Python script that contains the node configuration files and an installer script. The script will take an argument to a device to install to, e.g. /dev/sdb, and overwrite everything on that device -- :) BE CAREFUL (:",
    )
    outgroup.add_argument(
        "--outtar",
        type=Path,
        help="A path to write a tarball of the node configuration files to. If this is provided, write a tarball that contains the node configuration files. The tarball not be compressed.",
    )

    # The --force parser
    forceparser = argparse.ArgumentParser(add_help=False)
    forceparser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing files. This is dangerous, as it will overwrite any changes you have made to the files.",
    )

    # The 'new' subcommand
    new_parser = subparsers.add_parser("new", parents=[forceparser, outparser], help="Create a new node")

    new_parser.add_argument("nodename", help="The name you want to use for this node")

    default_hostname = "{nodename}.example.com"
    new_parser.add_argument(
        "--hostname",
        default=default_hostname,
        help=f"The hostname to use for this node. Defaults to {default_hostname.format(nodename='NODENAME')}",
    )

    new_parser.add_argument("--flavor-text", default="", help="Flavor text for the node")

    new_parser.add_argument(
        "--psynetip",
        type=CIDRv4,
        required=True,
        help="The IP address to use for this node on psynet, in a format like 42.0.66.6/69. Add this address to `ansible/cloudformation/PsynetZone.cfn.yml` and deploy it. Make sure this is unique!",
    )

    psynet_groups_default = "psyopsOS"
    new_parser.add_argument(
        "--psynet-groups",
        nargs="+",
        default=psynet_groups_default,
        help="The groups to add this node to, comma separated. Defaults to %(default)s",
    )

    new_parser.add_argument(
        "--mac-address",
        default="00:00:00:00:00:00",
        help="The MAC address of the node's NIC card. If this is not provided it defaults to %(default)s, and you must edit the resulting mactab file with the real address or the network will not be configured properly.",
    )

    new_parser.add_argument(
        "--serial",
        default="00000000",
        help="The serial number or service tag for the hardeware. Defaults to all %(default)s.",
    )

    # The "save" subcommand
    save_parser = subparsers.add_parser(
        "save", parents=[forceparser, outparser], help="Save an existing node's configuration"
    )
    save_parser.add_argument(
        "nodename",
        help="The name of the existing node.",
    )

    # The "delete" subcommand
    delete_parser = subparsers.add_parser("delete", help="Delete an existing node's configuration.")
    delete_parser.add_argument(
        "nodename",
        help="The name of the node to delete.",
    )

    return parser


def main():
    """Create a new node in the progfiguration site"""
    parser = makeparser()
    parsed = parser.parse_args()

    logger.setLevel("DEBUG")

    if parsed.debug:
        sys.excepthook = idb_excepthook

    if not (parsed.pyproject_root / "pyproject.toml").exists():
        raise RuntimeError(
            f"pyproject.toml not found at {parsed.pyproject_root}, please specify the path to the root of the pyproject.toml file with the --pyproject-root option. Note that you should generally be running this script from an editable install of a git checkout, where this will not be necessary."
        )

    sitewrapper.set_progfigsite_by_filepath(Path(progfiguration_blacksite.__file__), "progfiguration_blacksite")

    def _save_result(nodesec: NodeSecrets):
        """Save the result of a new or save subcommand according to the parsed arguments"""
        if parsed.outscript:
            nodesec.save_installer_script(parsed.outscript)
        elif parsed.outtar:
            cmd = ["tar", "-C", nodesec.secroot, "-cf", parsed.outtar.absolute()] + [f.name for f in nodesec.files]
            subprocess.run(cmd, check=True)
        else:
            nodesec.save_directory(Path(parsed.outdir.format(nodename=parsed.nodename)))

    if parsed.subcommand == "delete":
        nodemod_file = None
        try:
            nodemod = sitewrapper.site_submodule(f"nodes.{parsed.nodename}")
            nodemod_file = nodemod.__file__
        except ModuleNotFoundError:
            print(f"Node module at nodes.{parsed.nodename} does not exist.")
        except Exception:
            # This might happen if the module exists but is broken
            nodes_dir = os.path.dirname(sitewrapper.site_submodule("nodes").__file__)
            maybe_nodemod_file = os.path.join(nodes_dir, f"{parsed.nodename}.py")
            if os.path.exists(maybe_nodemod_file):
                nodemod_file = maybe_nodemod_file
        if nodemod_file:
            os.unlink(nodemod_file)
        try:
            tksecrets.gopass_rm(f"progfiguration/nodeage/{parsed.nodename}.age")
        except subprocess.CalledProcessError:
            print(f"No psynet secrets found for {parsed.nodename}.")
        try:
            tksecrets.gopass_rm(f"psyopsOS/sshhostkeys/{parsed.nodename}")
        except subprocess.CalledProcessError:
            print(f"No age secrets found for {parsed.nodename}.")
        try:
            tksecrets.gopass_rm(f"psynet/{parsed.nodename}.crt")
            tksecrets.gopass_rm(f"psynet/{parsed.nodename}.key")
        except subprocess.CalledProcessError:
            print(f"No ssh host secrets found for {parsed.nodename}.")

        return

    # Remaining subcommands take --outdir / --outscript

    if parsed.outscript:
        if parsed.outscript.exists() and not parsed.force:
            raise RuntimeError(f"{parsed.outscript} already exists, refusing to overwrite it.")
    elif parsed.outtar:
        if parsed.outtar.exists() and not parsed.force:
            raise RuntimeError(f"{parsed.outtar} already exists, refusing to overwrite it.")
    else:
        outdir = Path(parsed.outdir.format(nodename=parsed.nodename))
        if outdir.exists() and not parsed.force:
            raise RuntimeError(f"{outdir} already exists, refusing to overwrite it.")
        outdir.mkdir(parents=True, exist_ok=True)

    if parsed.subcommand == "new":
        if check_node_exists(parsed.nodename) and not parsed.force:
            raise RuntimeError(f"Node {parsed.nodename} already exists, refusing to overwrite it.")
        with tempfile.TemporaryDirectory() as nodesecdir, tksecrets.psynetca() as psynetca:
            nodesec = NodeSecrets.new(
                secroot=Path(nodesecdir),
                nodename=parsed.nodename,
                psynetip=parsed.psynetip,
                psynet_groups=parsed.psynet_groups,
                nebula_ca_directory=psynetca,
                mac_address=parsed.mac_address,
            )
            nodemgmt.make_node_inventory_file(
                nodename=parsed.nodename,
                hostname=parsed.hostname.format(nodename=parsed.nodename),
                flavor_text=parsed.flavor_text,
                age_pubkey=nodesec.agepub,
                ssh_host_fingerprint=nodesec.sshhostprint,
                mac_address=parsed.mac_address,
                serial=parsed.serial,
            )
            _save_result(nodesec)
        return

    if parsed.subcommand == "save":
        if not check_node_exists(parsed.nodename):
            raise RuntimeError(f"Node {parsed.nodename} does not exist.")
        with tempfile.TemporaryDirectory() as nodesecdir:
            nodesec = NodeSecrets.from_existing(secroot=Path(nodesecdir), nodename=parsed.nodename)
            _save_result(nodesec)
        return

    raise parser.error(f"Unknown subcommand {parsed.subcommand}")
