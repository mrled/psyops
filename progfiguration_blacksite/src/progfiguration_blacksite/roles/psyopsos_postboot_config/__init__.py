"""Configure Alpine after its boot scripts"""

from dataclasses import dataclass
import re
import shutil
import textwrap
import time
from typing import List

from progfiguration.cmd import magicrun
from progfiguration.inventory.roles import ProgfigurationRole
from progfiguration.localhost import LocalhostLinux, authorized_keys

from progfiguration_blacksite.sitelib import alpine_release_v


# These users must be present in userdb
_users = [
    {
        "name": "mrled",
        "password": r"$6$123$AYzXO51WqiIiN0TbNAhGsCru1.tid3VGQmAdfFRz8NajosFP73tF7Btq4huF82nMDDQ0arcNnmcZ6KYiuvqje/",
        "pubkeys": [
            r"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ/zN5QLrTpjL1Qb8oaSniRQSwWpe5ovenQZOLyeHn7m conspirator@PSYOPS",
            r"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMN/4Rdkz4vlGaQRvhmhLhkaH0CfhNnoggGBBknz17+u mrled@haluth.local",
        ],
        "shell": "/bin/bash",
    }
]


def configure_user(localhost: LocalhostLinux, name: str, password: str, pubkeys: List[str], shell=None):
    exists = False
    with open("/etc/passwd") as fp:
        for line in fp.readlines():
            if line and re.match(f"{name}:", line):
                exists = True
                break
    if not exists:
        cmd = ["useradd", "--create-home", "--user-group", "--password", password]
        if shell:
            cmd += ["--shell", shell]
        cmd += [name]
        magicrun(cmd)
    if pubkeys:
        authorized_keys.add_idempotently(localhost, name, pubkeys)


def set_timezone(timezone: str):
    magicrun(f"apk add tzdata")

    shutil.copyfile(f"/usr/share/zoneinfo/{timezone}", "/etc/localtime")
    with open(f"/etc/timezone", "w") as tzfp:
        tzfp.write(timezone)

    magicrun("rc-service ntpd restart")

    # We can remove tzdata if we want to
    # <https://wiki.alpinelinux.org/wiki/Setting_the_timezone>
    # magicrun(f"apk del tzdata")


def set_apk_repositories(localhost: LocalhostLinux):
    """Set /etc/apk/repositories

    Note that by default ONLY the cdrom repo exists,
    so we have to add even the regular main repo.

    The psyopsOS repo is also added by 000-psyopsOS-postboot.start.
    Updating it here requires updating it there too.
    """
    add_repos = [
        f"https://dl-cdn.alpinelinux.org/alpine/{alpine_release_v()}/main",
        f"https://dl-cdn.alpinelinux.org/alpine/{alpine_release_v()}/community",
        "@edgemain       https://dl-cdn.alpinelinux.org/alpine/edge/main",
        "@edgecommunity  https://dl-cdn.alpinelinux.org/alpine/edge/community",
        "@edgetesting    https://dl-cdn.alpinelinux.org/alpine/edge/testing",
        f"https://psyops.micahrl.com/apk/{alpine_release_v()}/psyopsOS",
    ]
    localhost.linesinfile("/etc/apk/repositories", add_repos)

    # If we update here, apk often fails with an exit code of 6.
    # I think this happens because 000-psyopsOS-postboot.start has just updated it before running progfiguration.
    # apk update says you should not need to do this normally anyway.
    #
    # result = magicrun("apk update", check=False, log_output=True)
    # if result.returncode != 0:
    #     logger.info(f"apk update failed with code {result.returncode}")
    #     logger.info(f"apk update stdout: {result.stdout}")
    #     logger.info(f"apk update stderr: {result.stderr}")
    #     secs = 15
    #     logger.info(f"Sleeping {secs} seconds before trying again")
    #     time.sleep(secs)
    #     magicrun("apk update", log_output=True)


def install_base_packages():
    """Install things we expect to be on every psyopsOS macahine"""
    packages = [
        "py3-pip",
    ]
    magicrun(["apk", "add"] + packages)


_psyopsOS_path_sh = r"""\
# Append "$1" to $PATH when not already in.
# Copied from Alpine /etc/profile, which copied from Arch.
__psyopsOS_append_path() {
    case ":$PATH:" in
        *:"$1":*)
            ;;
        *)
            PATH="${PATH:+$PATH:}$1"
            ;;
    esac
}

__psyopsOS_append_path "$HOME/.local/bin"
"""


@dataclass(kw_only=True)
class Role(ProgfigurationRole):
    timezone: str

    remote_syslog_host: str
    remote_syslog_port: int
    syslogd: str

    def configure_busybox_syslogd(self):
        self.localhost.set_file_contents(
            "/etc/conf.d/syslog",
            textwrap.dedent(
                f"""\
                SYSLOGD_OPTS="-t -L -R {self.remote_syslog_host}:{self.remote_syslog_port}"
                """
            ),
            owner="root",
            group="root",
            mode=0o644,
        )

        # TODO: this generates a lot of junk when progfiguration tries to log to syslog it's been stopped
        magicrun("rc-service syslog restart")
        # We do this even though the OS is stateless so that rc-status knows it should be running
        magicrun("rc-update add syslog default")

    def apply(self):
        set_timezone(self.timezone)

        if self.syslogd == "busybox":
            self.configure_busybox_syslogd()
        else:
            raise NotImplementedError(f"Unknown syslog client type {self.client_syslogd}")

        set_apk_repositories(self.localhost)

        install_base_packages()

        self.localhost.set_file_contents(
            "/etc/profile.d/psyopsOS_path.sh",
            _psyopsOS_path_sh,
            "root",
            "root",
            0o0644,
            0o0755,
        )

        magicrun("rc-service crond start")

        for user in _users:
            configure_user(self.localhost, **user)

        # We have a common pattern of /psyopsos-data/roles/ROLENAME being a "role_dir".
        # This should be chmod 755 so that all users can read it.
        # Most roles with create a subdir chmod 700,
        # so if this isn't created first, /psyopsos-data/roles
        # will be 700 and other users can't read it.
        self.localhost.makedirs("/psyopsos-data/roles", owner="root", mode=0o755)
