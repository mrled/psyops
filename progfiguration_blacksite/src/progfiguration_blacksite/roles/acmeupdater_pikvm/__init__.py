"""Add an ACME updater for a pikvm NAS"""

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Optional

from progfiguration.inventory.roles import ProgfigurationRole

from progfiguration_blacksite.sitelib import line_in_crontab


@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    legodir: Path
    aws_region: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_zone: str
    acmedns_email: str
    domain: str
    """The domain to get certs from Let's Encrypt for"""
    pikvmuser: str = "root"
    """Uername to use to ssh to the PiKVM"""
    pikvmhost: Optional[str] = None
    """The name to use to connect to the PiKVM; defaults to the domain"""
    acmeupdater_user: str
    acmeupdater_sshid_name: str
    capthook_hooksdir: Path
    capthook_user: str

    pikvm_ssh_keyscan: str
    """A line for known_hosts that authenticates the PiKVM"""

    def apply(self):
        pikvmhost = self.pikvmhost or self.domain

        gotent = self.localhost.users.getent_user(self.acmeupdater_user)
        homedir = gotent.homedir

        self.localhost.linesinfile(
            homedir / ".ssh" / "known_hosts",
            [self.pikvm_ssh_keyscan],
            create_owner=self.acmeupdater_user,
            create_group=gotent.gid,
            create_mode=0o0600,
            create_dirmode=0o0700,
        )

        # A script that calls lego and copies the certs to the PiKVM
        acmedns_updater_script_path = Path(f"/usr/local/bin/acmeupdater_pikvm_{self.domain}.sh")

        self.localhost.temple(
            self.role_file("acmeupdater_pikvm.sh.temple"),
            str(acmedns_updater_script_path),
            {
                "legodir": str(self.legodir),
                "aws_region": self.aws_region,
                "aws_access_key_id": self.aws_access_key_id,
                "aws_secret_access_key": self.aws_secret_access_key,
                "aws_zone": self.aws_zone,
                "acmedns_email": self.acmedns_email,
                "pikvmdomain": self.domain,
                "pikvmuser": self.pikvmuser,
                "pikvmhost": pikvmhost,
                "ssh_id_name": self.acmeupdater_sshid_name,
            },
            owner="root",
            mode=0o755,
        )
        self.localhost.write_sudoers(
            f"/etc/sudoers.d/acmeupdater_pikvm_{self.domain}",
            f"ALL ALL=({self.acmeupdater_user}) NOPASSWD: {str(acmedns_updater_script_path)}\n",
        )

        # Run the script once now.
        # We don't check any errors or return output here.
        # start_new_session=True keeps script being killed when the parent process exits,
        # like nohup/disown.
        # Ensures the script is run at least once.
        run_once_command = ["sudo", "-u", self.acmeupdater_user, str(acmedns_updater_script_path)]
        subprocess.Popen(run_once_command, start_new_session=True)

        self.localhost.temple(
            self.role_file("hook.json.temple"),
            str(self.capthook_hooksdir / f"acmeupdater_pikvm_{self.domain}.hook.json"),
            {
                "job_name": f"acmeupdater_pikvm_{self.domain}",
                "job_user": self.acmeupdater_user,
                "updater_script": str(acmedns_updater_script_path),
            },
            owner=self.capthook_user,
            mode=0o600,
        )
        subprocess.run("rc-service capthook restart", shell=True, check=True)

        # Run the script at 04:23 on Tuesdays -- a non-round-number time to be nice to Let's Encrypt
        crontabline = f"23 4 * * 2 {str(acmedns_updater_script_path)}"
        line_in_crontab(self.acmeupdater_user, crontabline)
