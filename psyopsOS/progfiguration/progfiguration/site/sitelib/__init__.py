"""Site-specific functions"""

import subprocess

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
