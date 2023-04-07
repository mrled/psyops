"""Set up a data disk"""

import os
import subprocess

from progfiguration import logger
from progfiguration.inventory.roles import ProgfigurationRole


class Role(ProgfigurationRole):
    """Install the capthook platform for arbitrary web hooks"""

    defaults = {
        "username": "capthook",
        "groupname": "capthook",
        "port": 8098,
    }

    constants = {
        "hooks_subpath": "webhooks",
    }

    def apply(
        self,
        username: str,
        groupname: str,
        port: int,
    ):
        self.localhost.users.add_service_account(username, groupname, home=True, shell="/bin/sh")
        subprocess.run(["apk", "add", "webhook"], check=True)
        homedir = self.localhost.users.getent_user(username).homedir
        hooks_dir = os.path.join(homedir, self.constants["hooks_subpath"])

    def results(
        self,
        username: str,
        groupname: str,
        port: int,
    ):
        homedir = self.localhost.users.getent_user(username).homedir
        return {
            "username": username,
            "groupname": groupname,
            "homedir": homedir,
            "hooksdir": os.path.join(homedir, self.constants["hooks_subpath"]),
            "port": port,
        }
