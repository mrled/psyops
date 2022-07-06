"""Configure Alpine after its boot scripts"""

import json
import os
import shutil
import subprocess
import textwrap

from progfiguration.facts import PsyopsOsNode


defaults = {}


def set_timezone(timezone: str):
    subprocess.run(f"apk add tzdata", shell=True, check=True)

    shutil.copyfile(f"/usr/share/zoneinfo/{timezone}", "/etc/localtime")
    with open(f"/etc/timezone", 'w') as tzfp:
        tzfp.write(timezone)

    subprocess.run("rc-service ntpd restart", shell=True, check=True)

    # We can remove tzdata if we want to
    # <https://wiki.alpinelinux.org/wiki/Setting_the_timezone>
    # subprocess.run(f"apk del tzdata", shell=True, check=True)


def apply(node: PsyopsOsNode, timezone: str):

    # We must use --bytes bc of a bug in util-linux
    # https://github.com/util-linux/util-linux/issues/1636
    lsblk = json.loads(subprocess.run(["lsblk", "--json", "--output-all", "--bytes"], capture_output=True, check=True).stdout)

    bootfs = None
    for blkdev in lsblk['blockdevices']:
        if str(blkdev.get("label")).startswith("psyopsos-boot"):
            bootfs = blkdev
            break
    if not bootfs:
        raise Exception("Could not find boot device from lsblk")

    bootfs_apks = os.path.join(bootfs['mountpoint'], "apks")

    # Set /etc/apk/repositories
    repos = textwrap.dedent(
        f"""\
        {bootfs_apks}
        https://dl-cdn.alpinelinux.org/alpine/{node.alpine_release_v}/main
        https://dl-cdn.alpinelinux.org/alpine/{node.alpine_release_v}/community
        @edgemain       http://dl-cdn.alpinelinux.org/alpine/edge/main
        @edgecommunity  http://dl-cdn.alpinelinux.org/alpine/edge/community
        @edgetesting    http://dl-cdn.alpinelinux.org/alpine/edge/testing
        """
    )
    node.set_file_contents("/etc/apk/repositories", repos)
    subprocess.run("apk update", shell=True, check=True)

    set_timezone(timezone)
