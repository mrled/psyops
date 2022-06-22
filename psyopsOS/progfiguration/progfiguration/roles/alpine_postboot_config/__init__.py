"""Configure Alpine after its boot scripts"""

import subprocess
import textwrap

from progfiguration.facts import PsyopsOsNode


defaults = {}


def apply(node: PsyopsOsNode):

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
