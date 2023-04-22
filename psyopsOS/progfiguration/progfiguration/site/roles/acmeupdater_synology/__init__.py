"""Add an ACME updater for a Synology NAS"""

from dataclasses import dataclass
from pathlib import Path
import subprocess

from progfiguration.inventory.roles import ProgfigurationRole


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

    def apply(self):
        homedir = self.localhost.users.getent_user(self.acmeupdater_user).homedir
        syno_tls_update_script_path = homedir / "syno-tls-update.py"
        self.localhost.cp(
            self.role_file("syno-tls-update.py"),
            str(syno_tls_update_script_path),
            owner=self.acmeupdater_user,
            mode=0o755,
        )
        self.localhost.temple(
            self.role_file("acmeupdater_synology.sh.temple"),
            "/usr/local/bin/acmeupdater_synology.sh",
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
        self.localhost.temple(
            self.role_file("hook.json.temple"),
            str(self.capthook_hooksdir / "acmeupdater_synology.hook.json"),
            {
                "job_name": "acmeupdater_synology",
                "job_user": self.acmeupdater_user,
                "updater_script": "/usr/local/bin/acmeupdater_synology.sh",
            },
            owner=self.acmeupdater_user,
            mode=0o600,
        )
        subprocess.run("rc-service capthook restart", shell=True, check=True)

    def results(self):
        return {}
