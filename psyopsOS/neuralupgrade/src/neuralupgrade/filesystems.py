from dataclasses import dataclass
import json
import subprocess
import time
from typing import Optional

from neuralupgrade import logger
from neuralupgrade.coginitivedefects import MultiError
from neuralupgrade.dictify import Dictifiable


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


class MockMount:
    """Mock Mount context manager."""

    def __init__(self, path):
        self.path = path

    def __enter__(self):
        return self.path

    def __exit__(self, exc_type, exc_value, traceback):
        pass


class Mount:
    """A context manager for mounting filesystems.

    When the context manager is entered, it will mount the filesystem at the specified mountpoint
    with the specified ro/rw option.

    When the context manager is exited, it will try to return it to the original state:
    unmounted, mounted ro, etc.

    When the device is mounted in more than one place,
    or not on the fstab mountpoint,
    we have to unmount it from all mountpoints and remount it to the fstab mountpoint,
    and then unmount it when the context manager is exited.
    """

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
            umount_retry(existing_mountpoints[0]["target"])
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
        cleanup_errs = []
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
            cleanup_errs.append(e)

        # Properly handle exceptions, whether they were raised from the context manager block (exc_typ/exc_value),
        # or from the cleanup block (cleanup_errs).
        # This __exit__ function is called whether the block exited normally or with an exception,
        # so we need to differentiate between the two cases.
        if cleanup_errs:
            cleanup_err_msg = (
                f"Encountered exceptions when exiting Mount context manager for {self.device} on {self.mountpoint}"
            )
            if exc_type:
                raise MultiError(cleanup_err_msg, cleanup_errs) from exc_value
            raise MultiError(cleanup_err_msg, cleanup_errs)

        # If there was an exception in the block,
        # return False to indicate that we want the exception to be raised.
        # We're not supposed to 'raise' such an exception ourselves here)
        #
        # <https://docs.python.org/3/reference/datamodel.html#object.__exit__>
        # "Note that __exit__() methods should not reraise the passed-in exception; this is the caller’s responsibility."
        # If I understand correctly, the "caller" is just Python itself.
        if exc_type:
            return False

    def get_existing_mountpoints(self):
        """Return a list of mountpoints where the device is mounted"""
        findmnt_json = subprocess.run(["findmnt", self.device, "--json"], capture_output=True)
        logger.debug(f"findmnt --json {self.device} -> {findmnt_json.stdout.decode('utf-8')}")
        if findmnt_json.returncode == 0:
            return json.loads(findmnt_json.stdout)["filesystems"]


class Filesystem(Dictifiable):
    """A psyopsOS filesystem

    Arguments:
    label:          The label of the filesystem
    device:         The device path of the filesystem
                    If not specified, looked up from label
    mountpoint:     The mountpoint of the filesystem
                    If not specified, looked up by device and then by label in /etc/fstab
    mockmount:      If True, do not ever actually attempt to mount the filesystem,
                    but use the contents of the "mountpoint" directory as-is.
                    Useful for test mocking and examples.
                    Requires that label and mountpoint are specified.
                    The label and device are not used and may be fake values.
    """

    def __init__(
        self, label: str = "", device: str = "", mountpoint: str = "", writable: bool = False, mockmount: bool = False
    ):
        if mockmount:
            if not (label and mountpoint):
                raise ValueError("Must specify label and mountpoint for mockmount")
            if not device:
                device = f"/dev/mock/{label}"
        self.label = label
        self._device = device
        self._mountpoint = mountpoint
        self.mockmount = mockmount

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
        if self.mockmount:
            return MockMount(self.mountpoint)
        return Mount(self.device, self.mountpoint, writable)

    def __repr__(self):
        return f"Filesystem(label={self.label!r}, device={self.device!r}, mountpoint={self.mountpoint!r})"

    def dictify(self) -> dict:
        """Convert the object to a dictionary."""
        return {
            "label": self.label,
            "device": self.device,
            "mountpoint": self.mountpoint,
            "mockmount": self.mockmount,
        }


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
    """Return the booted side (A or B), by reading from the kernel command line.

    Expect this to be the A or B label.
    """
    with open("/proc/cmdline") as f:
        cmdline = f.read()
    for arg in cmdline.split():
        if arg.startswith("psyopsos="):
            thisside = arg.split("=")[1]
            logger.debug(f"Booted side is {thisside}")
            return thisside
    raise ValueError("Could not determine booted side")


def flipside(side: str, filesystems: Filesystems) -> str:
    """Given one side (A or B), return the other side."""
    if side not in [filesystems.a.label, filesystems.b.label]:
        raise ValueError(f"Unknown side {side}")
    opposite = filesystems.a.label if side == filesystems.b.label else filesystems.b.label
    logger.debug(f"Side {opposite} is opposite {side}")
    return opposite


@dataclass
class Sides:
    """A dataclass to hold the booted and nonbooted sides"""

    booted: str
    nonbooted: str

    def __repr__(self):
        return f"Sides(booted={self.booted!r}, nonbooted={self.nonbooted!r})"

    @classmethod
    def detect(cls, filesystems: Filesystems) -> "Sides":
        """Detect the booted and nonbooted sides"""
        return cls(activeside(), flipside(activeside(), filesystems))
