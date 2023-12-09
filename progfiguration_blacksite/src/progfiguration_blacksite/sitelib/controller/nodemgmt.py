"""Node management"""
import textwrap
from progfiguration.temple import Temple


node_py_temple = Temple(
    textwrap.dedent(
        """\
    from progfiguration.inventory.nodes import InventoryNode

    node = InventoryNode(
        address="{$}hostname",
        user="root",
        age_pubkey="{$}age_pubkey",
        ssh_host_fingerprint="{$}ssh_host_fingerprint",
        sitedata=dict(
            notes="",
            flavortext="{$}flavor_text",
            psy0mac="{$}psy0mac",
            serial="{$}serial",
        ),
        roles=dict,
    )
    """
    )
)
"""The template for the node.py file"""


def get_node_installer_script_temple(
    nodename: str,
    age_key: str,
    mactab: str,
    nebula_key: str,
    nebula_crt: str,
    ssh_host_key: str,
) -> Temple:
    """Get the template for the node installer script"""

    node_installer_script_temple = Temple(
        r"""#!/usr/bin/env python3
'''Install the {$}nodename node's configuration'''
from argparse import ArgumentParser
from subprocess import run
from os import makedirs

files = {}
files["nodename"] = '''{$}nodename
'''
files["age.key"] = '''{$}age_key
'''
files["mactab"] = '''{$}mactab
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
    return node_installer_script_temple.substitute(
        nodename=nodename,
        age_key=age_key,
        mactab=mactab,
        nebula_key=nebula_key,
        nebula_crt=nebula_crt,
        ssh_host_key=ssh_host_key,
    )
