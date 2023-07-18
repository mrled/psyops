"""Add an ACME updater for a Synology NAS"""

from dataclasses import dataclass
from pathlib import Path
import subprocess
import textwrap

from progfiguration.inventory.roles import ProgfigurationRole

from progfigsite.sitelib import line_in_crontab


@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    legodir: Path
    aws_region: str
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_zone: str
    acmedns_email: str
    domain: str
    synology_user: str
    synology_host: str
    acmeupdater_user: str
    capthook_hooksdir: Path
    capthook_user: str

    # A suffix to identify this job (in case we have multiple Synology boxes)
    job_suffix: str

    # We run the cron job once a week.
    # Offset it by this many seconds to be nice to Let's Encrypt.
    cron_delay_seconds: int = 60 * 19

    # A line for known_hosts that authenticates the synology
    synology_ssh_keyscan: str

    def apply(self):
        gotent = self.localhost.users.getent_user(self.acmeupdater_user)
        homedir = gotent.homedir

        self.localhost.linesinfile(
            homedir / ".ssh" / "known_hosts",
            [self.synology_ssh_keyscan],
            create_owner=self.acmeupdater_user,
            create_group=gotent.gid,
            create_mode=0o0600,
            create_dirmode=0o0700,
        )

        # A script that we will copy to the synology to apply certificate updates
        syno_tls_update_script_path = homedir / "syno-tls-update.py"

        # A script that calls lego, copies the certs to the synology, and runs the syno_tls_update_script
        acmedns_updater_script_path = Path(f"/usr/local/bin/acmeupdater_synology_{self.job_suffix}.sh")

        self.localhost.cp(
            self.role_file("syno-tls-update.py"),
            str(syno_tls_update_script_path),
            owner=self.acmeupdater_user,
            mode=0o755,
        )
        self.localhost.temple(
            self.role_file("acmeupdater_synology.sh.temple"),
            str(acmedns_updater_script_path),
            {
                "legodir": str(self.legodir),
                "aws_region": self.aws_region,
                "aws_access_key_id": self.aws_access_key_id,
                "aws_secret_access_key": self.aws_secret_access_key,
                "aws_zone": self.aws_zone,
                "syno_tls_update_script": str(syno_tls_update_script_path),
                "acmedns_email": self.acmedns_email,
                "domain": self.domain,
                "synology_user": self.synology_user,
                "synology_host": self.synology_host,
            },
            owner="root",
            mode=0o755,
        )
        self.localhost.write_sudoers(
            f"/etc/sudoers.d/acmeupdater_synology_{self.job_suffix}",
            f"ALL ALL=({self.acmeupdater_user}) NOPASSWD: {str(acmedns_updater_script_path)}\n",
        )
        self.localhost.temple(
            self.role_file("hook.json.temple"),
            str(self.capthook_hooksdir / f"acmeupdater_synology_{self.job_suffix}.hook.json"),
            {
                "job_name": f"acmeupdater_synology_{self.job_suffix}",
                "job_user": self.acmeupdater_user,
                "updater_script": str(acmedns_updater_script_path),
            },
            owner=self.capthook_user,
            mode=0o600,
        )
        subprocess.run("rc-service capthook restart", shell=True, check=True)

        # Run the script at 04:19 on Tuesdays -- a random time to be nice to Let's Encrypt
        crontabline = f"19 4 * * 2 {str(acmedns_updater_script_path)}"
        line_in_crontab(self.acmeupdater_user, crontabline)

    def results(self):
        return {}
