"""Configure the psynet overlay network"""

from dataclasses import dataclass
from pathlib import Path
import shutil

from progfiguration import logger
from progfiguration.cmd import magicrun
from progfiguration.inventory.roles import ProgfigurationRole

from progfiguration_blacksite.sitelib.users import add_managed_service_account


@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    # TODO: Keep these in the secret store instead of saving them to psyops-secret mount
    psynet_host_crt: Path = Path("/mnt/psyops-secret/mount/psynet.host.crt")
    psynet_host_key: Path = Path("/mnt/psyops-secret/mount/psynet.host.key")

    # This is the nebula admin ssh host key.
    # It provides debugging and nebula administrative access, but not shell.
    # This can be different from the host ssh key... but I have opted for simplicity.
    # TODO: generate a separate key for nebula admin ssh service.
    # psynet_nebula_admin_ssh_host_key: Path = Path("/mnt/psyops-secret/mount/ssh_host_ed25519_key")

    # nebulizer_pubkey: str

    def apply(self):

        if not self.psynet_host_crt.exists() or not self.psynet_host_key.exists():
            logger.error(f"psynet host key and/or cert does not exist, skipping psynet configuration")
            return

        # The package adds a user and group, but we want to control the UID/GID.
        add_managed_service_account("nebula", "nebula")

        magicrun("apk add nebula nebula-openrc")

        # Take advantage of built-in rc script functionality
        # Copying the rc script to nebula.psynet will caust it to look for /etc/nebula/psynet.yml automatically
        # It's ok to do this even if the psynet config file doesn't exist, it just won't start.
        self.localhost.cp("/etc/init.d/nebula", "/etc/init.d/nebula.psynet", "root", "root", 0o0755)

        # self.localhost.cp(
        #     self.psynet_nebula_admin_ssh_host_key, "/etc/nebula/psynet.ssh_host_ed25519_key", "nebula", "nebula", 0o0600
        # )

        self.localhost.makedirs("/etc/nebula", "nebula", "nebula", 0o0700)
        self.localhost.cp(
            self.psynet_host_crt,
            "/etc/nebula/psynet.host.crt",
            "nebula",
            "nebula",
            0o0600,
        )
        self.localhost.cp(
            self.psynet_host_key,
            "/etc/nebula/psynet.host.key",
            "nebula",
            "nebula",
            0o0600,
        )
        tmp_psynet_yml = "/tmp/nebula.psynet.yml"
        self.localhost.temple(
            self.role_file("psynet.yml.temple"),
            tmp_psynet_yml,
            {},
            # {
            #     "ssh_host_key_path": "/etc/nebula/psynet.ssh_host_ed25519_key",
            #     "nebulizer_pubkey": self.nebulizer_pubkey,
            # },
            "nebula",
            "nebula",
            0o0640,
        )
        self.localhost.cp(
            self.role_file("psynet.ca.crt"),
            "/etc/nebula/psynet.ca.crt",
            "nebula",
            "nebula",
            0o0600,
        )
        result = magicrun(f"nebula -test -config {tmp_psynet_yml}", check=False)
        if result.returncode != 0:
            raise Exception(f"nebula -test failed with code {result.returncode}, bad config file at {tmp_psynet_yml}")
        shutil.move(tmp_psynet_yml, "/etc/nebula/psynet.yml")

        magicrun("modprobe tun")
        # Read the config file in case we changed it.
        magicrun("rc-service nebula.psynet restart")
        # We do this even though the OS is stateless so that rc-status knows it should be running
        magicrun("rc-update add nebula.psynet default")
