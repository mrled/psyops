"""Set up a data disk"""

from dataclasses import dataclass, field
import os
import shutil
import subprocess
from typing import List, Optional

from progfiguration import logger
from progfiguration.inventory.roles import ProgfigurationRole
from progfiguration.localhost import LocalhostLinuxPsyopsOs


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


@dataclass
class Mount:
    device: str
    mountpoint: str
    filesystem: str
    options: List[str]
    dump: int
    fsck: int

    @classmethod
    def from_line(cls, line: str) -> "Mount":
        """Return a Mount from a line in /etc/fstab or /proc/mounts"""
        return cls(*line.split())


def is_mounted_device(devpath: str) -> Optional[Mount]:
    """If the device is mounted, return a Mount object representing it, otherwise None.

    We check to see if the devpath is the start of any string in /proc/mounts -- meaning that if
    you pass /dev/sda and /dev/sda1 is mounted, we will return True.

    Return only the first mountpoint we find, regardless of whether the device is also mounted
    elsewhere.
    """
    with open("/proc/mounts") as fp:
        mounts = fp.read()
    for line in mounts.split("\n"):
        if line.startswith(devpath):
            return Mount.from_line(line)
    return None


def is_mountpoint(path: str) -> bool:
    """Return true if a path is a mountpoint for a currently mounted filesystem"""
    mtpt = subprocess.run(["mountpoint", path], check=False, capture_output=True)
    return mtpt.returncode == 0


@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    underlying_device: str = "/dev/sda"
    mountpoint: str = "/psyopsos-data"
    vgname: str = "psyopsos_datadiskvg"
    lvname: str = "datadisklv"
    lvsize: str = r"100%FREE"
    fslabel: str = "psyopsos_data"
    wipefs_if_no_vg: bool = False
    wipe_after_mounting: list[str] = field(default_factory=list)
    ramoffload: bool = False
    ramoffload_size_gb: int = 32
    ramoffload_directories: List[str] = field(default_factory=lambda: ["/usr"])

    def apply(self):

        # Just cheating a bit not have to change this messy function too much
        # We are going to deprecate it soon anyway
        underlying_device = self.underlying_device
        mountpoint = self.mountpoint
        vgname = self.vgname
        lvname = self.lvname
        lvsize = self.lvsize
        fslabel = self.fslabel
        wipefs_if_no_vg = self.wipefs_if_no_vg
        wipe_after_mounting = self.wipe_after_mounting
        ramoffload = self.ramoffload
        ramoffload_size_gb = self.ramoffload_size_gb
        ramoffload_directories = self.ramoffload_directories

        # We always wipe the scratch directory, even if it's been overridden
        wipe_after_mounting.append("scratch")

        subprocess.run(f"apk add e2fsprogs e2fsprogs-extra lvm2", shell=True, check=True)
        subprocess.run("rc-service lvm start", shell=True, check=True)

        if subprocess.run(f"vgs {vgname}", shell=True, check=False).returncode != 0:
            logger.info(f"Volume group {vgname} does not exist")
            if not wipefs_if_no_vg:
                msg = f"Refusing to wipe filesystem on {underlying_device}, because wipefs_if_no_vg is False"
                logger.error(msg)
                raise Exception(msg)
            mounted = is_mounted_device(underlying_device)
            if mounted:
                msg = (
                    f"Refusing to wipe filesystem on {underlying_device}, because it is mounted to {mounted.mountpoint}"
                )
                logger.error(msg)
                raise Exception(msg)
            logger.info(f"Wiping filesystems on {underlying_device}...")
            subprocess.run(f"wipefs --all {underlying_device}", shell=True, check=True)
            logger.info(f"Creating {vgname} volume group on {underlying_device}...")
            subprocess.run(f"vgcreate {vgname} {underlying_device}", shell=True, check=True)

        lvs = subprocess.run(f"lvs {vgname}", shell=True, check=False, capture_output=True)
        if lvname not in lvs.stdout.decode():
            logger.info(f"Creating volume {lvname} on vg {vgname}...")
            # lvcreate is very annoying as it uses --extents for percentages and --size for absolute values
            szflag = ""
            if "%" in lvsize:
                szflag = "-l"
            else:
                szflag = "-L"
            subprocess.run(f"lvcreate {szflag} {lvsize} -n {lvname} {vgname}", shell=True, check=True)

        mapper_device = f"/dev/mapper/{vgname}-{lvname}"

        e2l = subprocess.run(f"e2label {mapper_device}", shell=True, capture_output=True)
        if e2l.returncode != 0 or fslabel not in e2l.stdout.decode():
            logger.info(f"Creating filesystem on {mapper_device}...")
            subprocess.run(f"mkfs.ext4 -F -L {fslabel} {mapper_device}", shell=True, check=True)

        if not is_mountpoint(mountpoint):
            logger.info(f"Mounting {mapper_device} on {mountpoint}...")
            os.makedirs(mountpoint, mode=0o755, exist_ok=True)
            subprocess.run(f"mount {mapper_device} {mountpoint}", shell=True, check=True)

            # Take care that we are operating on lists of strings
            if isinstance(wipe_after_mounting, str):
                raise Exception("wipe_after_mounting must be a list of strings but it is a string")
            for subpath in wipe_after_mounting:
                if subpath.startswith("/"):
                    raise Exception(
                        f"wipe_after_mounting subpath {subpath} must not start with / - it is relative to {mountpoint}"
                    )
                if not isinstance(subpath, str):
                    raise Exception(f"wipe_after_mounting subpath {subpath} must be a string but is a {type(subpath)}")
            for subpath in wipe_after_mounting:
                path = os.path.join(mountpoint, subpath)
                if os.path.exists(path):
                    logger.info(f"Removing path {path} after mounting {mountpoint}...")
                    shutil.rmtree(path)

        self.localhost.makedirs(f"{mountpoint}/scratch", "root", "root", 0o1777)

        if ramoffload:
            logger.info(f"Enabling ramoffload to {mountpoint}...")
            setup_ramoffload(self.localhost, mountpoint, ramoffload_size_gb, ramoffload_directories)
        else:
            logger.info("Will not enable ramoffload")
