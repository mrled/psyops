"""psyopsOS docker host

Concerns handled by this role
- Docker needs a large filesystem for most uses,
  and won't work if its data dir is on the psyopsOS ramdisk.
- We could use overlayfs or ramoffload for the default docker data dir at /var/lib/docker,
  but this is incompatible with the overlay2 Docker storage driver.
- The overlay2 Docker storage driver is faster/more efficient than the vfs driver,
  which is what you get by default
  (not sure if that's always true on Alpine or just bc I was using ramoffload).

This role must be run after the datadisk_v2 role
so that /psyopsos-data/scratch is available.
"""


import string
from dataclasses import dataclass

from progfiguration.cmd import magicrun
from progfiguration.inventory.roles import ProgfigurationRole


openrc_docker_conf_tmpl = string.Template(
    """\
DOCKER_OPTS="--data-root=$dataroot --storage-driver=overlay2"
"""
)


@dataclass(kw_only=True)
class Role(ProgfigurationRole):
    dataroot: str = "/psyopsos-data/scratch/docker"

    def apply(self):
        packages = [
            "docker",
            "docker-compose",
            "docker-openrc",
        ]
        magicrun(["apk", "add", *packages])
        self.localhost.makedirs(self.dataroot, owner="root", mode=0o710)
        self.localhost.set_file_contents(
            "/etc/conf.d/docker",
            openrc_docker_conf_tmpl.substitute(dataroot=self.dataroot),
            owner="root",
            group="root",
            mode=0o644,
        )
        magicrun("rc-update add docker default", check=False)
        magicrun("rc-service docker start")
