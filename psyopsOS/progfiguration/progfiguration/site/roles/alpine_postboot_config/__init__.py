"""Configure Alpine after its boot scripts"""

from dataclasses import dataclass
import re
import shutil
from typing import List

from progfiguration.cmd import run
from progfiguration.inventory.roles import ProgfigurationRole
from progfiguration.localhost import LocalhostLinuxPsyopsOs, authorized_keys


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


def configure_user(localhost: LocalhostLinuxPsyopsOs, name: str, password: str, pubkeys: List[str], shell=None):
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
        run(cmd)
    if pubkeys:
        authorized_keys.add_idempotently(localhost, name, pubkeys)


def set_timezone(timezone: str):
    run(f"apk add tzdata")

    shutil.copyfile(f"/usr/share/zoneinfo/{timezone}", "/etc/localtime")
    with open(f"/etc/timezone", "w") as tzfp:
        tzfp.write(timezone)

    run("rc-service ntpd restart")

    # We can remove tzdata if we want to
    # <https://wiki.alpinelinux.org/wiki/Setting_the_timezone>
    # run(f"apk del tzdata")


def set_apk_repositories(localhost: LocalhostLinuxPsyopsOs):
    """Set /etc/apk/repositories

    Note that by default ONLY the cdrom repo exists, so we have to add even the regular main repo.
    """
    apk_repositories_old = localhost.get_file_contents("/etc/apk/repositories")
    apk_repositories_new = apk_repositories_old
    add_repos = [
        f"https://dl-cdn.alpinelinux.org/alpine/{localhost.alpine_release_v}/main",
        f"https://dl-cdn.alpinelinux.org/alpine/{localhost.alpine_release_v}/community",
        "@edgemain       https://dl-cdn.alpinelinux.org/alpine/edge/main",
        "@edgecommunity  https://dl-cdn.alpinelinux.org/alpine/edge/community",
        "@edgetesting    https://dl-cdn.alpinelinux.org/alpine/edge/testing",
        "https://psyops.micahrl.com/apk/psyopsOS",
    ]
    for repo in add_repos:
        if repo not in apk_repositories_old:
            if apk_repositories_new[-1] != "\n":
                apk_repositories_new += "\n"
            apk_repositories_new += f"{repo}"
    if apk_repositories_new[-1] != "\n":
        apk_repositories_new += "\n"
    localhost.set_file_contents("/etc/apk/repositories", apk_repositories_new, "root", "root", 0o0644)
    run("apk update")


def install_base_packages():
    """Install things we expect to be on every psyopsOS macahine"""
    packages = [
        "py3-pip",
    ]
    run(["apk", "add"] + packages)


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

    def apply(self):

        set_timezone(self.timezone)

        set_apk_repositories(self.localhost)

        install_base_packages()

        self.localhost.set_file_contents(
            "/etc/profile.d/psyopsOS_path.sh", _psyopsOS_path_sh, "root", "root", 0o0644, 0o0755
        )

        run("rc-service crond start")

        for user in _users:
            configure_user(self.localhost, **user)
