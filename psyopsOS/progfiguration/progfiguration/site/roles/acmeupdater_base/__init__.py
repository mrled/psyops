"""Base ACME updater

Installs lego and configures it to be run by other roles.

* Creates a user and group for running lego.
* Adds an SSH key for the user, so that it can connect to other servers.
* Adds a /usr/local/bin/acmeupdater_wraplego.py script,
  which determines whether to run 'lego run' or 'lego renew'
  and sets a few nice defaults.
  Other roles can rely on this script.

Actually running lego for a specific purpose is handled by other roles.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil

from progfiguration.inventory.roles import ProgfigurationRole
from progfiguration.ssh import generate_pubkey


@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    role_dir: Path
    username: str = "acmeupdater"
    groupname: str = "acmeupdater"
    sshkey: str

    @property
    def legodir(self):
        return self.role_dir / "lego"

    @property
    def homedir(self) -> Path:
        return self.localhost.users.getent_user(self.username).homedir

    def apply(self):
        self.localhost.users.add_service_account(self.username, self.groupname, home=True, shell="/bin/sh")
        self.localhost.makedirs(self.role_dir, self.username, self.groupname, 0o700)
        sshdir = self.homedir / ".ssh"
        self.localhost.makedirs(sshdir, self.username, self.groupname, 0o700)
        sshkey_path = sshdir / "id_acmeupdater"
        sshkey_pub_path = sshkey_path.with_suffix(".pub")
        with sshkey_path.open("w") as f:
            f.write(self.sshkey)
        with sshkey_pub_path.open("w") as f:
            f.write(generate_pubkey(self.sshkey))
        self.localhost.cp(
            self.role_file("wraplego.py.txt"), "/usr/local/bin/acmeupdater_wraplego.py", "root", "root", 0o0755, 0o0755
        )

    def results(self):
        return {
            "legodir": self.legodir,
            "sshkey_pub": generate_pubkey(self.sshkey),
        }
