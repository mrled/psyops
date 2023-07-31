"""Configure an Onion admin service

Contains code from genuineDeveloperBrain
<https://tor.stackexchange.com/a/23674>
"""


from dataclasses import dataclass
from pathlib import Path
import textwrap

from progfiguration import logger
from progfiguration.cmd import magicrun
from progfiguration.inventory.roles import ProgfigurationRole
from progfiguration.progfigtypes import AnyPathOrStr

from progfiguration_blacksite.roles.onion_admin.set_onion_key import create_hidden_service_files
from progfiguration_blacksite.roles.onion_admin.ssh_keyparse import _ssh_key_parse


def convert_ssh_ed25519_key_to_onion_hidden_service(
    ssh_ed25519_key_path: AnyPathOrStr, hidden_service_dir: AnyPathOrStr, tor_username: str
):
    """Convert an ed25519 SSH key to a Tor Hidden Service key

    This is probably not a good idea! idk anything, I'm crypto stupid.

    Equivalent to:
    ssh_key_ed25519_seed = magicrun(f"ssh-keyparse.py /mnt/psyops-secret/mount/ssh_host_ed25519_key -x")
    magicrun(f"onion-key-helper.py --force --private-key {ssh_key_ed25519_seed} {str(hidden_service_dir)}")
    """

    if not isinstance(ssh_ed25519_key_path, Path):
        ssh_ed25519_key_path = Path(ssh_ed25519_key_path)

    # Hack around the user-friendly 'ssh_key_parse()' (no leading underscore) function
    # to get the raw bytes of the SSH key without dealing with a temp file
    # or having to change any code from the original module.
    with ssh_ed25519_key_path.open("rb") as f:
        ed25519_privkey_bytes = _ssh_key_parse(None, f, False)

    # The ed25519 SSH key is 64 bytes: 32 bytes of public key, followed by 32 bytes of seed.
    ed25519_public_key = ed25519_privkey_bytes[32:]
    ed25519_privkey_seed = ed25519_privkey_bytes[:32]

    onion_address = create_hidden_service_files(
        ed25519_privkey_seed,
        ed25519_public_key,
        hidden_service_dir,
        tor_username,
        overwrite=True,
    )

    return onion_address


@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    # Port that SSH is listening on already
    host_ssh_port: int = 22
    # Address that SSH is listening on already
    # (by default SSH is on all addresses so localhost works)
    host_ssh_address: str = "127.0.0.1"
    # Port that SSH will be exposed on via Tor
    tor_ssh_port: int = 22

    def apply(self):

        packages = [
            "py3-pynacl",
            "tor",
        ]
        magicrun(["apk", "add", *packages])
        magicrun("rc-update add tor default", check=False)

        toruser = self.localhost.users.getent_user("tor")

        self.localhost.cp(self.role_file("ssh_keyparse.py"), "/usr/local/bin/ssh-keyparse.py", mode=0o755)
        self.localhost.cp(self.role_file("set_onion_key.py"), "/usr/local/bin/set-onion-key.py", mode=0o755)

        hidden_service_dir = Path("/var/lib/tor/services/admin")
        self.localhost.makedirs(hidden_service_dir, "tor", toruser.gid, 0o700)

        onion_address = convert_ssh_ed25519_key_to_onion_hidden_service(
            "/mnt/psyops-secret/mount/ssh_host_ed25519_key", hidden_service_dir, toruser.name
        )
        logger.info(f"Admin SSH onion address: {onion_address}")

        self.localhost.linesinfile(
            "/etc/tor/torrc",
            [
                # Log debug messages - Tor Project recommends against this as it may expose info about users
                # "Log notice file /var/log/tor/notices.log",
                "DataDirectory /var/lib/tor",
                r"%include /etc/tor/torrc.d/*.conf",
            ],
            toruser.uid,
            toruser.gid,
            0o600,
        )
        self.localhost.makedirs("/etc/tor/torrc.d", toruser.uid, toruser.gid, 0o700)

        # While testing, it can be handy to also expose the Telepathy service,
        # by adding the following to the same admin.service.conf file:
        #   HiddenServicePort 7453 127.0.0.1:7453
        self.localhost.set_file_contents(
            "/etc/tor/torrc.d/admin.service.conf",
            textwrap.dedent(
                f"""\
                HiddenServiceDir /var/lib/tor/services/admin
                HiddenServicePort {self.tor_ssh_port} {self.host_ssh_address}:{self.host_ssh_port}
                """
            ),
            toruser.uid,
            toruser.gid,
            0o600,
            0o700,
        )

        magicrun("rc-service tor restart")
