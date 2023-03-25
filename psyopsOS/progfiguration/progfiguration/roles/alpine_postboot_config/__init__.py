"""Configure Alpine after its boot scripts"""

import os.path
import pwd
import re
import shutil
import subprocess
from typing import List

from progfiguration.localhost import LocalhostLinuxPsyopsOs, authorized_keys


defaults = {
    "devd": "",
    "mdev_enable_psyopsos_by_sysfs_rules": True,
}


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
        subprocess.run(cmd, check=True)
    if pubkeys:
        authorized_keys.add_idempotently(localhost, name, pubkeys)


def set_timezone(timezone: str):
    subprocess.run(f"apk add tzdata", shell=True, check=True)

    shutil.copyfile(f"/usr/share/zoneinfo/{timezone}", "/etc/localtime")
    with open(f"/etc/timezone", "w") as tzfp:
        tzfp.write(timezone)

    subprocess.run("rc-service ntpd restart", shell=True, check=True)

    # We can remove tzdata if we want to
    # <https://wiki.alpinelinux.org/wiki/Setting_the_timezone>
    # subprocess.run(f"apk del tzdata", shell=True, check=True)


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
    subprocess.run("apk update", shell=True, check=True)


def install_base_packages():
    """Install things we expect to be on every psyopsOS macahine"""
    packages = [
        "py3-pip",
    ]
    subprocess.run(["apk", "add"] + packages, check=True)


def enable_mdev_by_sysfs_path_psyopsos_rules(localhost: LocalhostLinuxPsyopsOs):
    """Enable psyopsOS by-sysfs-path-psyopsos rules

    Configure mdev to use our custom rules for creating symlinks under /dev/disk/by-sysfs-path-psyopsos

    See psyopsOS/docs/persistent-device-names.md for full context
    """

    mdev_conf = localhost.get_file_contents("/etc/mdev.conf")

    for block_link in os.listdir("/sys/block"):
        # block_link will be something like "nvme0n1";
        # devices_path will be something like
        # '/sys/devices/pci0000:00/0000:00:1b.0/0000:01:00.0/nvme/nvme0/nvme0n1'
        devices_path = os.path.realpath(os.path.join(os.path.dirname(block_link), os.readlink(block_link)))

    with


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


def apply(localhost: LocalhostLinuxPsyopsOs, timezone: str, devd: str, mdev_enable_psyopsos_by_sysfs_path_rules: bool):

    set_timezone(timezone)

    set_apk_repositories(localhost)

    if devd:
        subprocess.run(["setup-devd", "-C", devd], shell=True, check=True)

    if mdev_enable_psyopsos_by_sysfs_path_rules:

    install_base_packages()

    localhost.set_file_contents("/etc/profile.d/psyopsOS_path.sh", _psyopsOS_path_sh, "root", "root", 0o0644, 0o0755)

    for user in _users:
        configure_user(localhost, **user)
