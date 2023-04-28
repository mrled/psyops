"""Email backup role"""

from dataclasses import dataclass
import os
from pathlib import Path
from progfiguration.cmd import run
import venv

from progfiguration.inventory.roles import ProgfigurationRole
from progfiguration.site.sitelib import line_in_crontab
from progfiguration.ssh import generate_pubkey


def install_vdirsyncer_venv():
    """Install vdirsyncer in a virtual environment"""
    venvdir = "/usr/local/venv/vdirsyncer"
    if os.path.exists(venvdir):
        return
    os.mkdir("/usr/local/venv", 0o755)
    venv.create(venvdir, with_pip=True, symlink=True, upgrade_deps=True)
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
        return self.localhost.users.getent_user(self.username).homedir

    def apply(self):
        run("apk add offlineimap")

        # There is an apk package for vdirsyncer, but it's in @edgecommunity and it requires Python 3.11 for some reason.
        # We have to install its prereqs first though.
        run("apk add libxml2 libxslt zlib")
        install_vdirsyncer_venv()

        self.localhost.temple(
            self.role_file("offlineimaprc.temple"),
            self.homedir / ".offlineimaprc",
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
        line_in_crontab(self.pullbackup_user, f"0 */6 * * * {pullbackup_email_script}")

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

    def results(self):
        return {}


"""
---

- name: Install hook
  template:
    src: hook.json.j2
    dest: "{{ capthook_webhooks_dir }}/{{ mailbackup_hook_name }}.hook.json"
    owner: "{{ capthook_user }}"
    group: "{{ capthook_user }}"
    mode: "0644"
  notify: restart capthook

"""
