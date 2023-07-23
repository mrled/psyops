"""Site-specific functions"""

from pathlib import Path
import secrets
import string
import subprocess
from typing import List

from progfiguration.localhost import LocalhostLinux


def get_crontab(user: str) -> list[str]:
    """Get a user's system crontab as an array of lines"""
    proc = subprocess.run(["crontab", "-l", "-u", user], text=True, capture_output=True)
    if proc.returncode == 0:
        return proc.stdout.splitlines()

    # busybox crontab returns 1 from "crontab -lu" if the user has no crontab, wtf
    # TODO: This shouldn't require class instantiation
    localhost = LocalhostLinux()
    if localhost.users.user_exists(user):
        return []

    raise ValueError(f"User {user} does not exist")


def set_crontab(user: str, crontab: list[str]):
    """Set a user's system crontab from an array of lines"""
    crontab_str = "\n".join(crontab) + "\n"
    subprocess.run(["crontab", "-", "-u", user], check=True, text=True, input=crontab_str)


def line_in_crontab(user: str, line: str, prepend: bool = False) -> bool:
    """Add a line to a user's system crontab

    This should work for any POSIX cron implementation;
    it doesn't rely on special directories like /etc/cron.d.
    In particular, it works on busybox crond which is the default crond on Alpine.

    If prepend is True, the line is added to the beginning of the crontab.
    (Useful for variables like MAILTO.)

    Returns True if the line was added, False if it was already present.
    """
    crontab = get_crontab(user)
    if line not in crontab:
        if prepend:
            crontab.insert(0, line)
        else:
            crontab.append(line)
        set_crontab(user, crontab)
        return True
    return False


def get_persistent_secret(secretfile: Path, length=24) -> str:
    """Get a persistent secret

    If the file exists, return its contents.
    Otherwise, generate a new secret, write it to the file, and return it.

    When creating a new secret file, it will be owned and only readable by root.

    This is intended as an internal way for progfiguration to get secrets
    that the user doesn't need to know,
    but which shouldn't change after deployment unnecessarily,
    like database passwords where progfiguration is deploying both the application and its database.
    """
    # TODO: This shouldn't require class instantiation
    localhost = LocalhostLinux()

    # Generate Sonic backend password
    if secretfile.exists():
        secret = secretfile.read_text().strip()
    else:
        alphabet = string.ascii_letters + string.digits
        secret = "".join(secrets.choice(alphabet) for i in range(length))
        localhost.set_file_contents(
            secretfile,
            secret,
            owner="root",
            group="root",
            mode=0o0600,
        )

    return secret


def alpine_release_str(self) -> str:
    return LocalhostLinux().get_file_contents("/etc/alpine-release")


def alpine_release(self) -> List[int]:
    return [int(n) for n in alpine_release_str().split(".")]


def alpine_release_v(self) -> str:
    """If /etc/alpine-release is '3.16.0', this returns 'v3.16'."""
    maj, min, _ = alpine_release()
    return f"v{maj}.{min}"
