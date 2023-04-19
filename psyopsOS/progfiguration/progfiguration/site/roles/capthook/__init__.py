"""Set up a data disk"""

import os
from pathlib import Path
import shutil
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

    rolepkg = __package__

    @property
    def hooksdir(self):
        return self.homedir / "hooks"

    @property
    def homedir(self):
        return Path("/home/capthook")

    def apply(
        self,
        username: str,
        groupname: str,
        port: int,
    ):
        self.localhost.users.add_service_account(username, groupname, home=str(self.homedir), shell="/bin/sh")
        subprocess.run(["apk", "add", "webhook"], check=True)
        self.localhost.cp(self.role_file("hookbuilder.py"), self.hooksdir / "hookbuilder.py")
        self.localhost.temple(
            self.role_file("whoami.hook.json.temple"),
            self.hooksdir / "whoami.hook.json",
            owner=username,
            template_args={},
            group=groupname,
        )
        self.localhost.temple(
            self.role_file("showmeurhooks.hook.json.temple"),
            self.hooksdir / "showmeurhooks.hook.json",
            template_args={"hooksdir": str(self.hooksdir)},
            owner=username,
            group=groupname,
        )
        self.localhost.cp(
            self.role_file("capthook.openrc.init"),
            "/etc/init.d/capthook",
            owner="root",
            group="root",
            mode=0o0755,
        )
        self.localhost.temple(
            self.role_file("capthook.openrc.conf.temple"),
            "/etc/conf.d/capthook",
            template_args={
                "username": username,
                "groupname": groupname,
                "port": port,
                "hooksdir": str(self.hooksdir),
                "hooks_json": str(self.hooksdir / "hooks.json"),
                "hookbuilder": str(self.hooksdir / "hookbuilder.py"),
            },
            owner="root",
            group="root",
            mode=0o0644,
        )

    def results(
        self,
        username: str,
        groupname: str,
        port: int,
    ):
        return {
            "username": username,
            "groupname": groupname,
            "homedir": self.homedir,
            "hooksdir": self.hooksdir,
            "port": port,
        }
