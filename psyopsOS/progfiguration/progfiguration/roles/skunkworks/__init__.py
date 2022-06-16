"""The skunkworks role.

This role is special - it's where I do research and development
"""

import datetime
import subprocess
import textwrap
from typing import Any, Dict

from progfiguration.facts import PsyopsOsNode


def apply(node: PsyopsOsNode, variables: Dict[str, Any]):

    # Set /etc/apk/repositories
    repos = textwrap.dedent(
        f"""\
        /media/cdrom/apks
        https://dl-cdn.alpinelinux.org/alpine/{node.alpine_release_v}/main
        https://dl-cdn.alpinelinux.org/alpine/{node.alpine_release_v}/community
        """
    )
    node.set_file_contents("/etc/apk/repositories", repos)
    subprocess.run("apk update", shell=True, check=True)

    # Set a temp file for testing
    node.set_file_contents("/tmp/progfigurated", f"{datetime.datetime.now()}\n")
