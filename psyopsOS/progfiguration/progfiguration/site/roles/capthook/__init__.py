"""Set up a data disk"""

import os
import subprocess
from typing import Any, Dict, List

from progfiguration import logger
from progfiguration.localhost import LocalhostLinuxPsyopsOs


raise NotImplementedError("TODO: Rewrite this to use the new progfiguration API")
# This requires a working get_role_results function from progfiguration.inventory.roles


defaults = {
    "username": "capthook",
    "groupname": "capthook",
    "port": 8098,
}


constants = {
    "hooks_subpath": "webhooks",
}


def apply(
    localhost: LocalhostLinuxPsyopsOs,
    username: str,
    groupname: str,
    port: int,
):
    """Install the capthook platform for arbitrary web hooks"""

    localhost.users.add_service_account(username, groupname, home=True, shell="/bin/sh")
    subprocess.run(["apk", "add", "webhook"], check=True)
    homedir = localhost.users.getent_user(username).homedir
    hooks_dir = os.path.join(homedir, constants["hooks_subpath"])


def results(
    localhost: LocalhostLinuxPsyopsOs,
    username: str,
    groupname: str,
    port: int,
) -> Dict[str, Any]:

    homedir = localhost.users.getent_user(username).homedir
    return {
        "username": username,
        "groupname": groupname,
        "homedir": homedir,
        "hooksdir": os.path.join(homedir, constants["hooks_subpath"]),
        "port": port,
    }
