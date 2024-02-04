import json
import subprocess
import time
from typing import Optional

from neuralupgrade import logger
from neuralupgrade.coginitivedefects import MultiError


class UmountError(Exception):
    pass


def fstab() -> list[dict]:
    """Return the contents of /etc/fstab as a list of dicts"""
    filesystems = []
    with open("/etc/fstab") as f:
        for line in f.readlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            fs = {}
            (
                fs["device"],
                fs["mountpoint"],
                fs["fstype"],
                fs["options"],
                fs["dump"],
                fs["pass"],
            ) = line.split()
            filesystems.append(fs)
    return filesystems


def umount_retry(mountpoint: str, attempts: int = 2, sleepbetween: int = 1) -> None:
    """Unmount a mountpoint, retrying if it fails."""
    for attempt in range(attempts):
        if not subprocess.run(["mountpoint", "-q", mountpoint]).returncode == 0:
            logger.debug(f"{mountpoint} is not mounted, no need to umount")
            return
        subprocess.run(["umount", "-l", mountpoint])
        if not subprocess.run(["mountpoint", "-q", mountpoint]).returncode == 0:
            logger.debug(f"Umounted {mountpoint} (attempt {attempt + 1}/{attempts})")
            return
        logger.debug(
            f"Umounting {mountpoint} (attempt {attempt + 1}/{attempts}) failed, sleeping for {sleepbetween} seconds"
        )
        time.sleep(sleepbetween)
    raise UmountError(f"Could not umount {mountpoint} after {attempts} attempts")


class Mount:
    """A context manager for mounting filesystesm"""

    def __init__(self, device: str, mountpoint: str, writable: bool = False):
        self.device = device
        self.mountpoint = mountpoint
        self.writable = writable
        self.exit_remount_ro = False
        self.exit_leave_mounted = False

    def __enter__(self):
        # If the device is mounted anywhere aside from the fstab mountpoint
        # and/or is mounted ro, then we unmount it from all mountpoints and remount it rw to the fstab mountpoint.
        # POSIX doesn't allow different permissions like ro and rw for the same device mounted to two separate places,
        # so this is the simplest way to ensure that we can write to the device.
        existing_mountpoints = self.get_existing_mountpoints()

        mounted_ro = False
        mounted_rw = False

        if not existing_mountpoints:
            logger.debug(f"Filesystem on {self.device} is not mounted anywhere")
        elif len(existing_mountpoints) > 1:
            logger.debug(
                f"Filesystem on {self.device} is mounted at more than one mountpoint, unmounting all and will not remount"
            )
            for mountpoint in existing_mountpoints:
                umount_retry(mountpoint["target"])
        elif existing_mountpoints[0]["target"] != self.mountpoint:
            logger.debug(
                f"Filesystem on {self.device} is mounted at {existing_mountpoints[0]['target']} which is not the specified location, unmounting and will not remount"
            )
            umount_retry(mountpoint[0]["target"])
        else:
            options = existing_mountpoints[0]["options"].split(",")
            if "ro" in options:
                mounted_ro = True
            elif "rw" in options:
                mounted_rw = True

        if mounted_ro:
            if self.writable:
                logger.debug(f"Filesystem on {self.device} is mounted ro to {self.mountpoint}, remounting rw")
                self.exit_remount_ro = True
                subprocess.run(["mount", "-o", "rw,remount", self.mountpoint], check=True)
            else:
                logger.debug(f"Filesystem on {self.device} is mounted ro to {self.mountpoint}, no need to remount")
                self.exit_leave_mounted = True
        elif mounted_rw:
            logger.debug(f"Filesystem on {self.device} is mounted rw to {self.mountpoint}, no need to remount")
            self.exit_leave_mounted = True
        else:
            option = "rw" if self.writable else "ro"
            logger.debug(f"Filesystem on {self.device} is not mounted, mounting {option} to {self.mountpoint}")
            subprocess.run(["mount", "-o", option, self.device, self.mountpoint], check=True)

        return self.mountpoint

    def __exit__(self, exc_type, exc_value, traceback):
        exceptions = []
        try:
            if self.exit_remount_ro:
                logger.debug(f"Remounting filesystem on {self.device} ro")
                subprocess.run(["mount", "-o", "ro,remount", self.mountpoint], check=True)
            elif self.exit_leave_mounted:
                logger.debug(f"Leaving filesystem on {self.device} mounted")
            else:
                logger.debug(f"Unmounting filesystem on {self.device}")
                umount_retry(self.mountpoint)
        except Exception as e:
            exceptions.append(e)

        if exc_type:
            exceptions.append(exc_value)

        if exceptions:
            raise MultiError(
                f"Encountered exceptions when exiting Mount context manager for {self.device} on {self.mountpoint}",
                exceptions,
            )

    def get_existing_mountpoints(self):
        """Return a list of mountpoints where the device is mounted"""
        findmnt_json = subprocess.run(["findmnt", self.device, "--json"], capture_output=True)
        logger.debug(f"findmnt --json {self.device} -> {findmnt_json.stdout.decode('utf-8')}")
        filesystems = []
        if findmnt_json.returncode == 0:
            return json.loads(findmnt_json.stdout)["filesystems"]


class Filesystem:
    """A psyopsOS filesystem

    Arguments:
    label:          The label of the filesystem
    device:         The device path of the filesystem
                    If not specified, looked up from label
    mountpoint:     The mountpoint of the filesystem
                    If not specified, looked up by device and then by label in /etc/fstab
    """

    def __init__(self, label: str = "", device: str = "", mountpoint: str = "", writable: bool = False):
        self.label = label
        self._device = device
        self._mountpoint = mountpoint

    @property
    def device(self):
        """The device path of the filesystem"""
        if not self._device:
            blkid_L = subprocess.run(["blkid", "-L", self.label], check=True, capture_output=True)
            self._device = blkid_L.stdout.decode("utf-8").strip()
        return self._device

    def find_mountpoint_by_device(self) -> str:
        """Return the mountpoint of the filesystem by device via /etc/fstab"""
        for fs in fstab():
            if fs["device"] == self.device:
                return fs["mountpoint"]
        raise KeyError(f"Could not find {self.device} in fstab")

    def find_mountpoint_by_label(self) -> str:
        """Return the mountpoint of the filesystem by label via /etc/fstab"""
        for fs in fstab():
            if fs["device"] == f"LABEL={self.label}":
                return fs["mountpoint"]
        raise KeyError(f"Could not find {self.label} in fstab")

    @property
    def mountpoint(self):
        """The mountpoint of the filesystem"""
        if not self._mountpoint:
            try:
                self._mountpoint = self.find_mountpoint_by_device()
            except KeyError:
                try:
                    self._mountpoint = self.find_mountpoint_by_label()
                except KeyError:
                    pass
        if not self._mountpoint:
            raise KeyError(f"Could not find mountpoint for {self.label} or {self.device} in fstab")
        return self._mountpoint

    def mount(self, writable: bool = False):
        """A context manager for mounting the filesystem"""
        return Mount(self.device, self.mountpoint, writable)


class Filesystems:
    """The collection os psyopsOS filesystems"""

    def __init__(
        self, efisys: Optional[Filesystem] = None, a: Optional[Filesystem] = None, b: Optional[Filesystem] = None
    ):
        self.efisys = efisys or Filesystem(label="PSYOPSOSEFI")
        self.a = a or Filesystem(label="psyopsOS-A")
        self.b = b or Filesystem(label="psyopsOS-B")

    def bylabel(self, label: str) -> Filesystem:
        """Return the filesystem with the given label"""
        for fs in [self.efisys, self.a, self.b]:
            if fs.label == label:
                return fs
        raise ValueError(f"Unknown label {label}")

    def __getitem__(self, key: str) -> Filesystem:
        return getattr(self, key)

    def __repr__(self):
        return f"Filesystems({self.efisys!r}, {self.a!r}, {self.b!r})"


def activeside() -> str:
    """Return the booted side of a grubusb device, by reading from the kernel command line.

    Expect this to be the A or B label.
    """
    with open("/proc/cmdline") as f:
        cmdline = f.read()
    for arg in cmdline.split():
        if arg.startswith("psyopsos="):
            thisside = arg.split("=")[1]
            logger.debug(f"Booted side is {thisside}")
            return thisside
    raise ValueError("Could not determine booted side of grubusb device")


def flipside(side: str, filesystems: Filesystems) -> str:
    """Given one side of a grubusb image (A or B), return the other side."""
    if side not in [filesystems.a.label, filesystems.b.label]:
        raise ValueError(f"Unknown side {side}")
    opposite = filesystems.a.label if side == filesystems.b.label else filesystems.b.label
    logger.debug(f"Side {opposite} is opposite {side}")
    return opposite


def sides(filesystems: Filesystems) -> tuple[str, str]:
    """Return the booted side and the nonbooted side of a grubusb device (A or B)"""
    booted = activeside()
    return booted, flipside(booted, filesystems)
