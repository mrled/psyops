"""Set up a data disk"""

from dataclasses import dataclass, field
import os
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import List

from progfiguration import logger
from progfiguration.inventory.roles import ProgfigurationRole
from progfiguration.localhost import LocalhostLinux
from progfiguration.localhost.disks import is_mountpoint


def setup_ramoffload(
    localhost: LocalhostLinux,
    data_mountpoint: str,
    size_gb: int,
    directories: List[str],
    ramoffload_mount_path="/media/ramoffload",
    ramoffload_overlaid_path="/media/overlaid",
):
    """Set up ramoffload

    ramoffload makes use of Linux overlay filesystems.
    The same method is used by Alpine's lbu (though we do not use lbu here) --
    actually the commands to enable ramoffload came from the Alpine documentation:
    <https://wiki.alpinelinux.org/wiki/Alpine_local_backup>
    <https://wiki.alpinelinux.org/wiki/Raspberry_Pi>

    It allows us to install large packages to /usr without running out of RAM.

    It uses overlayfs and a ramdisk.
    We don't commit to the ramdisk, so it's just temp space that isn't persistent,
    but it's backed by the disk, so it doesn't consume RAM.

    We take the additional step of mounting the overlayfs under ramoffload_overlaid_path,
    and bind-mounting the paty under ramoffload_overlaid_path to the directory.
    This doesn't seem to be necessary for most cases,
    but is required when one of the directories is /var/lib/docker:
    <https://superuser.com/questions/1526682/docker-in-overlayroot-environment-invalid-cross-device-link>.
    I'm not sure why this is... maybe because we use overlayfs, and so does Docker?
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
        lowerdir = os.path.join(ramoffload_overlaid_path, dir_key)
        workdir = os.path.join(ramoffload_mount_path, f".work_{dir_key}")
        localhost.makedirs(upperdir, owner="root", mode=0o0755)
        localhost.makedirs(lowerdir, owner="root", mode=0o0755)
        localhost.makedirs(workdir, owner="root", mode=0o0755)
        fstab_entries = [
            f"overlay {lowerdir} overlay lowerdir={lowerdir},upperdir={upperdir},workdir={workdir} 0 0",
            f"{lowerdir} {directory} none bind 0 0",
        ]
        logger.info(f"Adding ramoffload for {directory} via fstab lines: {fstab_entries}")
        localhost.linesinfile("/etc/fstab", fstab_entries)
        subprocess.run(["mount", "-a"])

    logger.info("Finished configuring ramoffload")


@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    block_device: str = "/dev/sda"
    mountpoint: Path = Path("/psyopsos-data")
    # Anything path relative to the mountpoint in this list is wiped after mounting.
    # E.g. ['asdf/one/two', 'zxcv/three/four'] to remove /psyopsos-data/asdf/one/two and /psyopsos-data/zxczv/three/four.
    # If the filesystem is already mounted, nothing is removed.
    # Note that we ALWAYS wipe the "scratch" directory, even if its been overridden.
    wipe_after_mounting: list[str] = field(default_factory=list)
    ramoffload: bool = False
    ramoffload_size_gb: int = 32
    ramoffload_directories: List[str] = field(default_factory=lambda: ["/usr"])

    def apply(self):

        self.wipe_after_mounting.append("scratch")

        self.localhost.set_file_contents(
            "/etc/psyopsOS/roles/datadisk/env.sh",
            textwrap.dedent(
                f"""\
                PSYOPSOS_DATADISK_MOUNTPOINT="{self.mountpoint}"
                PSYOPSOS_DATADISK_DEVICE="{self.block_device}"
                """
            ),
        )
        self.localhost.cp(self.role_file("progfiguration-umount-datadisk.sh"), "/usr/local/sbin/", mode=0o755)

        if not is_mountpoint(str(self.mountpoint)):
            logger.info(f"Mounting {self.block_device} on {self.mountpoint}...")
            os.makedirs(str(self.mountpoint), mode=0o755, exist_ok=True)
            subprocess.run(f"mount {self.block_device} {self.mountpoint}", shell=True, check=True)

            # Take care that we are operating on lists of strings
            if isinstance(self.wipe_after_mounting, str):
                raise Exception("wipe_after_mounting must be a list of strings but it is a string")
            for subpath in self.wipe_after_mounting:
                if subpath.startswith("/"):
                    raise Exception(
                        f"wipe_after_mounting subpath {subpath} must not start with / - it is relative to {self.mountpoint}"
                    )
                if not isinstance(subpath, str):
                    raise Exception(f"wipe_after_mounting subpath {subpath} must be a string but is a {type(subpath)}")

            for subpath in self.wipe_after_mounting:
                path = self.mountpoint.joinpath(subpath)
                if os.path.exists(path):
                    logger.info(f"Removing path {path} after mounting {self.mountpoint}...")
                    shutil.rmtree(path)

        self.localhost.makedirs(f"{self.mountpoint}/scratch", "root", "root", 0o1777)

        if self.ramoffload:
            logger.info(f"Enabling ramoffload to {self.mountpoint}...")
            setup_ramoffload(self.localhost, str(self.mountpoint), self.ramoffload_size_gb, self.ramoffload_directories)
        else:
            logger.info("Will not enable ramoffload")

    def results(self):
        return {
            "block_device": self.block_device,
            "mountpoint": self.mountpoint,
        }
