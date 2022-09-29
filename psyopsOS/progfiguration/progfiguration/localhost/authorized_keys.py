"""Working with authorized keys"""


import os
from dataclasses import dataclass
from typing import List

from progfiguration.localhost import LocalhostLinux


def get(localhost: LocalhostLinux, user: str) -> List[str]:
    """Get the authorized_keys contents for a user"""

    authorized_keys_file = os.path.expanduser(f"~{user}/.ssh/authorized_keys")
    try:
        authorized_keys = localhost.get_file_contents(authorized_keys_file, refresh=True)
        return authorized_keys.split("\n")
    except FileNotFoundError:
        return []


def add_idempotently(localhost: LocalhostLinux, user: str, lines: List[str]):
    """Add new lines to an authorized_keys file

    Create the file and .ssh directory if necessary
    """

    dot_ssh = os.path.expanduser(f"~{user}/.ssh")
    authorized_keys = os.path.join(dot_ssh, "authorized_keys")
    if not os.path.exists(authorized_keys):
        group = localhost.get_user_primary_group(user)
        if not os.path.exists(dot_ssh):
            localhost.makedirs(dot_ssh, user, group, 0o0700)
        localhost.set_file_contents(authorized_keys, "", user, group, 0o0644, 0o0755)

    localhost.linesinfile(authorized_keys, lines)
