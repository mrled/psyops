"""Set up a data disk"""

import os
import shutil
import subprocess

from progfiguration import logger
from progfiguration.nodes import PsyopsOsNode


defaults = {
    "underlying_device": "/dev/sda",
    "mountpoint": "/psyopsos-data",
    "vgname": "psyopsos_datadiskvg",
    "lvname": "datadisklv",
    # fslabel is max 16 chars
    "fslabel": "psyopsos_data",
    "wipefs_if_no_vg": False,
    # Anything path relative to the mountpoint in this list is wiped after mounting.
    # E.g. ['asdf/one/two', 'zxcv/three/four'] to remove /psyopsos-data/asdf/one/two and /psyopsos-data/zxczv/three/four.
    # If the filesystem is already mounted, nothing is removed.
    "wipe_after_mounting": ['scratch'],
}

appends = ['wipe_after_mounting']


def is_mountpoint(path: str) -> bool:
    """Return true if a path is a mountpoint for a currently mounted filesystem"""
    mtpt = subprocess.run(["mountpoint", path], check=False, capture_output=True)
    return mtpt.returncode == 0


def apply(
    node: PsyopsOsNode,
    underlying_device: str,
    mountpoint: str,
    vgname: str,
    lvname: str,
    fslabel: str,
    wipefs_if_no_vg: bool,
    wipe_after_mounting: None,
):

    subprocess.run(f"apk add e2fsprogs e2fsprogs-extra lvm2", shell=True, check=True)
    subprocess.run("rc-service lvm start", shell=True, check=True)

    if subprocess.run(f"vgs {vgname}", shell=True, check=False).returncode != 0:
        logger.info(f"Volume group {vgname} does not exist")
        if not wipefs_if_no_vg:
            msg = f"Refusing to wipe filesystem on {underlying_device}, because wipefs_if_no_vg is False"
            logger.error(msg)
            raise Exception(msg)
        logger.info(f"Wiping filesystems on {underlying_device}...")
        subprocess.run(f"wipefs --all {underlying_device}", shell=True, check=True)
        logger.info(f"Creating {vgname} volume group on {underlying_device}...")
        subprocess.run(f"vgcreate {vgname} {underlying_device}", shell=True, check=True)

    lvs = subprocess.run(f"lvs {vgname}", shell=True, check=False, capture_output=True)
    if lvname not in lvs.stdout.decode():
        logger.info(f"Creating volume {lvname} on vg {vgname}...")
        subprocess.run(f"lvcreate -l 100%FREE -n {lvname} {vgname}", shell=True, check=True)

    mapper_device = f"/dev/mapper/{vgname}-{lvname}"

    e2l = subprocess.run(f"e2label {mapper_device}", shell=True, capture_output=True)
    if e2l.returncode != 0 or fslabel not in e2l.stdout.decode():
        logger.info(f"Creating filesystem on {mapper_device}...")
        subprocess.run(f"mkfs.ext4 -F -L {fslabel} {mapper_device}", shell=True, check=True)

    if not is_mountpoint(mountpoint):
        logger.info(f"Mounting {mapper_device} on {mountpoint}...")
        os.makedirs(mountpoint, mode=0o755, exist_ok=True)
        subprocess.run(f"mount {mapper_device} {mountpoint}", shell=True, check=True)

        wipe_after_mounting = wipe_after_mounting or []
        for subpath in wipe_after_mounting:
            path = os.path.join(mountpoint, subpath)
            if os.path.exists(path):
                logger.info(f"Removing path {path} after mounting {mountpoint}...")
                shutil.rmtree(path)

    node.makedirs(f"{mountpoint}/scratch", "root", "root", 0o1777)
