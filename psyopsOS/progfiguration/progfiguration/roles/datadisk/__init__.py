"""Set up a data disk"""

import os
import subprocess

from progfiguration import logger
from progfiguration.facts import PsyopsOsNode
from progfiguration.inventory.invhelpers import Bunch
from progfiguration.roles import rolehelpers


defaults = {
    "underlying_device": "/dev/sda",
    "mountpoint": "/psyopsos-data",
    "vgname": "psyopsos_datadiskvg",
    "lvname": "datadisklv",
    # fslabel is max 16 chars
    "fslabel": "psyopsos_data",
}


def apply(
    node: PsyopsOsNode,
    underlying_device: str,
    mountpoint: str,
    vgname: str,
    lvname: str,
    fslabel: str,
):

    subprocess.run(f"apk add e2fsprogs e2fsprogs-extra lvm2", shell=True, check=True)
    subprocess.run("rc-service lvm start", shell=True, check=True)

    mtpt = subprocess.run(f"mountpoint {mountpoint}", shell=True, check=False, capture_output=True)
    if mtpt.returncode == 0:
        logger.debug(f"Data disk already mounted at {mountpoint}")
        return

    if subprocess.run(f"vgs {vgname}", shell=True, check=False).returncode != 0:
        subprocess.run(f"vgcreate {vgname} {underlying_device}", shell=True, check=True)

    lvs = subprocess.run(f"lvs {vgname}", shell=True, check=False, capture_output=True)
    if lvname not in lvs.stdout.decode():
        subprocess.run(f"lvcreate -l 100%FREE -n {lvname} {vgname}", shell=True, check=True)

    mapper_device = f"/dev/mapper/{vgname}-{lvname}"

    e2l = subprocess.run(f"e2label {mapper_device}", shell=True, capture_output=True)
    if e2l.returncode != 0 or fslabel not in e2l.stdout.decode():
        subprocess.run(f"mkfs.ext4 -L {fslabel} {mapper_device}", shell=True, check=True)

    os.makedirs(mountpoint, mode=0o755, exist_ok=True)
    subprocess.run(f"mount {mapper_device} {mountpoint}", shell=True, check=True)
