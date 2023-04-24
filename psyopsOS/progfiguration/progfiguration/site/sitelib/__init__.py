"""Site-specific functions"""

import subprocess


def line_in_crontab(user: str, line: str):
    """Add a line to a user's system crontab

    This should work for any POSIX cron implementation;
    it doesn't rely on special directories like /etc/cron.d.
    In particular, it works on busybox crond which is the default crond on Alpine.
    """

    crontab = subprocess.run(
        ["crontab", "-l", "-u", user], check=True, text=True, capture_output=True
    ).stdout.splitlines()
    if line not in crontab:
        crontab.append(line)
        crontab_str = "\n".join(crontab) + "\n"
        subprocess.run(["crontab", "-", "-u", user], check=True, text=True, input=crontab_str)
