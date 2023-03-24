"""Set up a data disk"""

import os
import shutil
import subprocess
import textwrap
from typing import List

from progfiguration import logger
from progfiguration.localhost import LocalhostLinuxPsyopsOs
from progfiguration.localhost.disks import is_mountpoint


defaults = {
    "block_device": "/dev/sda",
    "mountpoint": "/psyopsos-data",
    # Anything path relative to the mountpoint in this list is wiped after mounting.
    # E.g. ['asdf/one/two', 'zxcv/three/four'] to remove /psyopsos-data/asdf/one/two and /psyopsos-data/zxczv/three/four.
    # If the filesystem is already mounted, nothing is removed.
    "wipe_after_mounting": ["scratch"],
    # Add a ramoffload disk image
    # This disk image is NOT persisted from boot to boot
    "ramoffload": False,
    "ramoffload_size_gb": 32,
    "ramoffload_directories": [
        "/usr",
    ],
}

appends = ["wipe_after_mounting"]


def setup_ramoffload(
    localhost: LocalhostLinuxPsyopsOs,
    data_mountpoint: str,
    size_gb: int,
    directories: List[str],
    ramoffload_mount_path="/media/ramoffload",
):
    """Set up ramoffload

    ramoffload makes use of Linux overlay filesystems.
    The same method is used by Alpine's lbu (though we do not use lbu here) --
    actually the commands to enable ramoffload came from the Alpine documentation:
    <https://wiki.alpinelinux.org/wiki/Alpine_local_backup>
    <https://wiki.alpinelinux.org/wiki/Raspberry_Pi>

    It allows us to install large packages to /usr without running out of RAM.
    """

    if is_mountpoint(ramoffload_mount_path):
        # If this is already mounted, we assume everything else in this function has already been completed
        logger.info(f"Found that the ramoffload mountpoint {ramoffload_mount_path} is already mounted, nothing to do")
        return

    ramoffload_img_path = os.path.join(data_mountpoint, "overlays", "ramoffload.img")
    size_kb = size_gb * 1024 * 1024
    try:
        os.remove(ramoffload_img_path)
    except FileNotFoundError:
        pass
    localhost.makedirs(os.path.dirname(ramoffload_img_path))
    subprocess.run(
        ["dd", "if=/dev/zero", f"of={ramoffload_img_path}", "bs=1024", "count=0", f"seek={size_kb}"], check=True
    )
    subprocess.run(["mkfs.ext4", ramoffload_img_path])
    localhost.linesinfile(
        "/etc/fstab", [f"{ramoffload_img_path} {ramoffload_mount_path} ext4 rw,relatime,errors=remount-ro 0 0"]
    )
    localhost.makedirs(ramoffload_mount_path, owner="root", group="root", mode=0o0755)
    subprocess.run(["mount", ramoffload_mount_path])

    for directory in directories:
        # Create mount and work subdirs for each directory
        # See the Alpine documentation for a description of how this works:
        # <https://wiki.alpinelinux.org/wiki/Alpine_local_backup>
        subdir = directory.strip("/")
        # Subdirectories of /, like /usr or /var, will just use 'usr' or 'var' as their key.
        # More distant descendants, like /var/cache/whatever,
        # will replace inner / characters with underscores, resulting in a key like var_cache_whatever
        dir_key = subdir.replace("/", "_")
        upperdir = os.path.join(ramoffload_mount_path, dir_key)
        workdir = os.path.join(ramoffload_mount_path, f".work_{dir_key}")
        localhost.makedirs(upperdir, owner="root", mode=0o0755)
        localhost.makedirs(workdir, owner="root", mode=0o0755)
        fstab_entry = f"overlay {directory} overlay lowerdir={directory},upperdir={upperdir},workdir={workdir} 0 0"
        logger.info(f"Adding ramoffload for {directory} via fstab line: {fstab_entry}")
        localhost.linesinfile("/etc/fstab", [fstab_entry])
        subprocess.run(["mount", "-a"])

    logger.info("Finished configuring ramoffload")


def apply(
    localhost: LocalhostLinuxPsyopsOs,
    block_device: str,
    mountpoint: str,
    wipe_after_mounting: None,
    ramoffload: bool,
    ramoffload_size_gb: int,
    ramoffload_directories: List[str],
):

    localhost.set_file_contents(
        "/etc/psyopsOS/roles/datadisk/env.sh",
        textwrap.dedent(
            """\
            PSYOPSOS_DATADISK_MOUNTPOINT="{mountpoint}"
            PSYOPSOS_DATADISK_DEVICE="{block_device}"
            """
        ).format(mountpoint=mountpoint),
    )
    localhost.cp("progfiguration-umount-datadisk", "/usr/local/sbin/", mode=0o755)

    if not is_mountpoint(mountpoint):
        logger.info(f"Mounting {block_device} on {mountpoint}...")
        os.makedirs(mountpoint, mode=0o755, exist_ok=True)
        subprocess.run(f"mount {block_device} {mountpoint}", shell=True, check=True)

        # TODO: Don't require list flattening.
        # We are flattening the list here because it is a list of lists
        # Instead fix the caller to not make it pass a list of lists
        wipe_after_mounting = wipe_after_mounting or []
        wipes = [item for sublist in wipe_after_mounting for item in sublist]
        for subpath in wipes:
            path = os.path.join(mountpoint, subpath)
            if os.path.exists(path):
                logger.info(f"Removing path {path} after mounting {mountpoint}...")
                shutil.rmtree(path)

    localhost.makedirs(f"{mountpoint}/scratch", "root", "root", 0o1777)

    if ramoffload:
        logger.info(f"Enabling ramoffload to {mountpoint}...")
        setup_ramoffload(localhost, mountpoint, ramoffload_size_gb, ramoffload_directories)
    else:
        logger.info("Will not enable ramoffload")
