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
        @edgemain       http://dl-cdn.alpinelinux.org/alpine/edge/main
        @edgecommunity  http://dl-cdn.alpinelinux.org/alpine/edge/community
        @edgetesting    http://dl-cdn.alpinelinux.org/alpine/edge/testing
        """
    )
    node.set_file_contents("/etc/apk/repositories", repos)
    subprocess.run("apk update", shell=True, check=True)
