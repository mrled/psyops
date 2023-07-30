"""Email backup role"""

from dataclasses import dataclass
import os
from pathlib import Path
import venv

from progfiguration import logger
from progfiguration.cmd import run
from progfiguration.inventory.roles import ProgfigurationRole

from progfiguration_blacksite.sitelib import line_in_crontab


def install_vdirsyncer_venv():
    """Install vdirsyncer in a virtual environment"""
    venvdir = "/usr/local/venv/vdirsyncer"
    if os.path.exists(venvdir):
        return
    os.makedirs("/usr/local/venv", 0o755, exist_ok=True)
    venv.create(venvdir, with_pip=True, symlinks=True, upgrade_deps=True)
    run([f"{venvdir}/bin/pip", "install", "vdirsyncer"])
    os.symlink(f"{venvdir}/bin/vdirsyncer", "/usr/local/bin/vdirsyncer")


@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    role_dir: Path
    capthook_hooksdir: Path
    capthook_user: str
    job_suffix: str
    pullbackup_user: str

    cloudkey_hostname: str
    cloudkey_pubkey: str
    cloudkey_user: str

    @property
    def backuproot(self):
        return self.role_dir / "backups"

    @property
    def homedir(self) -> Path:
        return self.localhost.users.getent_user(self.pullbackup_user).homedir

    def apply(self):

        self.localhost.makedirs(self.role_dir, owner="root", mode=0o755)
        self.localhost.makedirs(self.backuproot / "backups", owner=self.pullbackup_user, mode=0o700)

        pullbackup_unifi_script = "/usr/local/bin/pullbackup_unifi.sh"
        self.localhost.temple(
            self.role_file("pullbackup_unifi.sh.temple"),
            pullbackup_unifi_script,
            {
                "cloudkey_user": self.cloudkey_user,
                "cloudkey_host": self.cloudkey_hostname,
                "backup_dest": self.backuproot,
                "sshid": self.homedir / ".ssh" / "id_pullbackup",
            },
            owner=self.pullbackup_user,
            mode=0o700,
        )

        line_in_crontab(self.pullbackup_user, f"MAILTO={self.pullbackup_user}", prepend=True)
        line_in_crontab(self.pullbackup_user, f"0 */6 * * * {pullbackup_unifi_script}")

        self.localhost.write_sudoers(
            "/etc/sudoers.d/pullbackup_unifi",
            f"ALL ALL=({self.pullbackup_user}) NOPASSWD: {pullbackup_unifi_script}",
        )

        self.localhost.linesinfile(
            self.homedir / ".ssh" / "known_hosts",
            f"{self.cloudkey_hostname} {self.cloudkey_pubkey}",
            create_owner=self.pullbackup_user,
            create_mode=0o600,
        )

        hookname = f"pullbackup_unifi_{self.job_suffix}"
        self.localhost.temple(
            self.role_file("hook.json.temple"),
            self.capthook_hooksdir / f"{hookname}.hook.json",
            {
                "hookname": hookname,
                "user": self.pullbackup_user,
                "script": pullbackup_unifi_script,
            },
            owner=self.capthook_user,
            mode=0o700,
        )

    def results(self):
        return {}
