"""Email backup role"""

from dataclasses import dataclass
import os
from pathlib import Path
import venv

from progfiguration import logger
from progfiguration.cmd import run
from progfiguration.inventory.roles import ProgfigurationRole
from progfiguration.site.sitelib import line_in_crontab


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

    me_micahrl_com_password: str
    role_dir: Path
    sshkey_path: Path
    capthook_hooksdir: Path
    capthook_user: str
    job_suffix: str
    pullbackup_user: str

    @property
    def backuproot(self):
        return self.role_dir / "backups"

    @property
    def homedir(self) -> Path:
        return self.localhost.users.getent_user(self.pullbackup_user).homedir

    def apply(self):
        run("apk add isync")

        # There is an apk package for vdirsyncer, but it's in @edgecommunity and it requires Python 3.11 for some reason.
        # We have to install its prereqs first though.
        run("apk add libxml2 libxslt zlib")
        install_vdirsyncer_venv()

        self.localhost.makedirs(self.role_dir, owner="root", mode=0o755)

        # Create required mbsync directories
        self.localhost.makedirs(
            self.backuproot / "mbsync" / "Personal" / "Inbox", owner=self.pullbackup_user, mode=0o700
        )

        self.localhost.temple(
            self.role_file("mbsyncrc.temple"),
            self.homedir / ".mbsyncrc",
            {
                "backuproot": str(self.backuproot),
                "me_micahrl_com_password": self.me_micahrl_com_password,
            },
            owner=self.pullbackup_user,
            mode=0o600,
        )

        self.localhost.temple(
            self.role_file("vdirsyncer_config.temple"),
            self.homedir / ".vdirsyncer/config",
            {
                "backuproot": str(self.backuproot),
                "mrled_fastmail_com_password": self.me_micahrl_com_password,
            },
            owner=self.pullbackup_user,
            mode=0o0600,
            dirmode=0o0700,
        )

        pullbackup_email_script = "/usr/local/bin/pullbackup_email.sh"

        self.localhost.temple(
            self.role_file("pullbackup_email.sh.temple"),
            pullbackup_email_script,
            {"username": self.pullbackup_user},
            owner=self.pullbackup_user,
            mode=0o700,
        )

        line_in_crontab(self.pullbackup_user, f"MAILTO={self.pullbackup_user}", prepend=True)

        # Run every 6 hours, at 38 minutes past the hour to spread load on the server(s)
        line_in_crontab(self.pullbackup_user, f"38 */6 * * * {pullbackup_email_script}")

        self.localhost.write_sudoers(
            "/etc/sudoers.d/pullbackup_email",
            f"ALL ALL=({self.pullbackup_user}) NOPASSWD: {pullbackup_email_script}",
        )

        self.localhost.temple(
            self.role_file("hook.json.temple"),
            self.capthook_hooksdir / f"pullbackup_email_{self.job_suffix}.hook.json",
            {
                "hookname": f"pullbackup_email_{self.job_suffix}",
                "username": self.pullbackup_user,
                "scriptpath": pullbackup_email_script,
            },
            owner=self.pullbackup_user,
            mode=0o700,
        )

        logger.info("Discovering vdirsyncer collections...")
        run("pullbackup_email.sh -m vdirsyncer-discover")

    def results(self):
        return {}
