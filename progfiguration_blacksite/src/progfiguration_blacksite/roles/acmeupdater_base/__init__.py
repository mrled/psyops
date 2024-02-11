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
from pathlib import Path

from progfiguration.cmd import magicrun
from progfiguration.inventory.roles import ProgfigurationRole
from progfiguration.ssh import generate_pubkey

from progfiguration_blacksite.sitelib import line_in_crontab
from progfiguration_blacksite.sitelib.users import add_managed_service_account


@dataclass(kw_only=True)
class Role(ProgfigurationRole):
    role_dir: Path
    username: str = "acmeupdater"
    groupname: str = "acmeupdater"
    sshkey: str

    sshid_name = "id_acmeupdater"
    """The name of the SSH key file in the user's .ssh directory."""

    @property
    def legodir(self):
        return self.role_dir / "lego"

    @property
    def homedir(self) -> Path:
        return self.localhost.users.getent_user(self.username).homedir

    def apply(self):
        add_managed_service_account(self.username, self.groupname, shell="/bin/sh")
        magicrun(["apk", "add", "lego"], check=True)
        self.localhost.makedirs(self.role_dir, self.username, self.groupname, 0o700)
        sshkey_path = self.homedir / ".ssh" / self.sshid_name
        sshkey_pub_path = sshkey_path.with_suffix(".pub")
        self.localhost.set_file_contents(sshkey_path, self.sshkey, self.username, self.groupname, 0o600, 0o700)
        self.localhost.set_file_contents(
            sshkey_pub_path, generate_pubkey(self.sshkey), self.username, self.groupname, 0o600
        )
        self.localhost.cp(
            self.role_file("wraplego.py.txt"), "/usr/local/bin/acmeupdater_wraplego.py", "root", "root", 0o0755, 0o0755
        )
        line_in_crontab(self.username, f"MAILTO={self.username}", prepend=True)

    def calculations(self):
        return {
            "legodir": self.legodir,
            "sshkey_pub": generate_pubkey(self.sshkey),
            "username": self.username,
            "sshid_name": self.sshid_name,
        }
