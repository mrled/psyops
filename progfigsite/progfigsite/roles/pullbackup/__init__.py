"""Base role for pulling backups from other hosts"""

from dataclasses import dataclass
from pathlib import Path

from progfiguration.inventory.roles import ProgfigurationRole
from progfiguration.ssh import generate_pubkey

from progfigsite.sitelib import line_in_crontab

@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    sshkey: str

    username: str = "pullbackup"
    groupname: str = "pullbackup"

    @property
    def homedir(self) -> Path:
        return Path(f"/home/{self.username}")

    @property
    def sshkey_path(self) -> Path:
        return self.homedir / ".ssh" / "id_pullbackup"

    def apply(self):
        self.localhost.users.add_service_account(self.username, self.groupname, home=self.homedir, shell="/bin/sh")
        sshkey_pub_path = self.sshkey_path.with_suffix(".pub")
        self.localhost.set_file_contents(self.sshkey_path, self.sshkey, self.username, self.groupname, 0o600, 0o700)
        self.localhost.set_file_contents(
            sshkey_pub_path, generate_pubkey(self.sshkey), self.username, self.groupname, 0o600
        )
        self.localhost.touch(self.homedir / ".ssh" / "known_hosts", self.username, self.groupname, 0o600)
        line_in_crontab(self.username, f"MAILTO={self.username}", prepend=True)

    def results(self):
        return {
            "sshkey_path": self.sshkey_path,
            "sshkey_pub": generate_pubkey(self.sshkey),
            "username": self.username,
        }
