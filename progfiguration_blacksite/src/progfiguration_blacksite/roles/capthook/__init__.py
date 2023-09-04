"""Run a webhooks service

Hooks are ddefined as JSON files which can be provided by other roles.
After a role adds a hook, it must restart the capthook service.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess

from progfiguration import logger
from progfiguration.inventory.roles import ProgfigurationRole


@dataclass(kw_only=True)
class Role(ProgfigurationRole):
    """Install the capthook platform for arbitrary web hooks"""

    username: str = "capthook"
    groupname: str = "capthook"
    port: int = 8098
    homedir: Path = Path("/home/capthook")
    hooks_subpath: str = "webhooks"

    @property
    def hooksdir(self):
        return self.homedir / "hooks"

    def apply(self):
        self.localhost.users.add_service_account(self.username, self.groupname, home=str(self.homedir), shell="/bin/sh")
        subprocess.run(["apk", "add", "webhook"], check=True)
        self.localhost.cp(
            self.role_file("hookbuilder.py"),
            self.hooksdir / "hookbuilder.py",
            owner=self.username,
            group=self.groupname,
            mode=0o0755,
        )
        self.localhost.temple(
            self.role_file("whoami.hook.json.temple"),
            self.hooksdir / "whoami.hook.json",
            owner=self.username,
            template_args={},
            group=self.groupname,
        )
        self.localhost.temple(
            self.role_file("list.hook.json.temple"),
            self.hooksdir / "showmeurhooks.hook.json",
            template_args={"hookid": "showmeurhooks", "hooksdir": str(self.hooksdir)},
            owner=self.username,
            group=self.groupname,
        )
        self.localhost.temple(
            self.role_file("list.hook.json.temple"),
            self.hooksdir / "list.hook.json",
            template_args={"hookid": "list", "hooksdir": str(self.hooksdir)},
            owner=self.username,
            group=self.groupname,
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
                "username": self.username,
                "groupname": self.groupname,
                "port": self.port,
                "hooksdir": str(self.hooksdir),
                "hooks_json": str(self.hooksdir / "hooks.json"),
                "hookbuilder": str(self.hooksdir / "hookbuilder.py"),
            },
            owner="root",
            group="root",
            mode=0o0644,
        )
        subprocess.run("rc-service capthook restart", shell=True, check=True)

    def calculations(self):
        return {
            "username": self.username,
            "groupname": self.groupname,
            "homedir": self.homedir,
            "hooksdir": self.hooksdir,
            "port": self.port,
        }
