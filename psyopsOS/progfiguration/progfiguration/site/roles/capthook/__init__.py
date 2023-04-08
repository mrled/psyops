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

    rolepkg = __package__

    def apply(
        self,
        username: str,
        groupname: str,
        port: int,
    ):
        self.localhost.users.add_service_account(username, groupname, home=True, shell="/bin/sh")
        subprocess.run(["apk", "add", "webhook"], check=True)
        homedir = self.localhost.users.getent_user(username).homedir
        hooksdir = os.path.join(homedir, self.constants["hooks_subpath"])
        self.localhost.cp(self.role_file("hookbuilder.py"), os.path.join(hooksdir, "hookbuilder.py"))
        self.localhost.temple(
            self.role_file("whoami.hook.json.temple"),
            os.path.join(hooksdir, "whoami.hook.json"),
            owner=username,
            template_args={},
            group=groupname,
        )
        self.localhost.temple(
            self.role_file("showmeurhooks.hook.json.temple"),
            os.path.join(hooksdir, "showmeurhooks.hook.json"),
            template_args={"hooksdir": hooksdir},
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
                "hooksdir": hooksdir,
                "hooks_json": os.path.join(hooksdir, "hooks.json"),
                "hookbuilder": os.path.join(hooksdir, "hookbuilder.py"),
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
        homedir = self.localhost.users.getent_user(username).homedir
        return {
            "username": username,
            "groupname": groupname,
            "homedir": homedir,
            "hooksdir": os.path.join(homedir, self.constants["hooks_subpath"]),
            "port": port,
        }
