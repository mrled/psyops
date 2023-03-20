"""Working with disks, filesystems, etc"""


import os
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from progfiguration import logger


@dataclass
class FilesystemSpec:
    # The type of filesystem -- requires a mkfs.{fstype} binary on the target system.
    fstype: str
    # The filesystem label (such as with e2label), different from GPT partition label.
    # This is probably mandatory for most cases, but can be set to empty string
    # (and label_opt set to empty string) to avoid setting a label,
    # which might be necessary for obscure filesystems.
    label: str
    # The option to pass to mkfs to set the label for this type of filesystem.
    # ext4 uses -L so it's the default.
    label_flag: str = "-L"
    # Options to pass to mkfs
    options: List[str] = field(default_factory=list)


@dataclass
class WholeDiskSpec:
    """A specification for a whole disk, to give an unpartitioned disk either a filesystem or a volume group"""

    # Either a device under /dev, or a device path under /sys
    #
    # If it's a device under /dev, it will be used as-is.
    # However, I'm not sure how well we can trust that device names will be stable between reboots.
    #
    # If it's a device path under /sys, it will be converted to a device under /dev.
    # **THIS ONLY WORKS ON THE TARGET SYSTEM**.
    # But the sys path should never change, even if the device name changes.
    #
    # The best way to find the syspath is to run `readlink -f /sys/class/block/{device}`
    # For instance:
    #   readlink -f /sys/class/block/sda
    #   /sys/devices/pci0000:00/0000:00:1f.2/ata1/host0/target0:0:0/0:0:0:0/block/sda
    #
    # (Don't worry that it ends in '../sda'; if the 'sda' part changes, we will still be able to find the device.)
    _device: str
    # Format the disk with this filesystem; mutually exclusive with volgroup
    filesystem: Optional[FilesystemSpec] = None
    # Add the disk to this volume group; mutually exclusive with filesystem
    volgroup: Optional[str] = None
    # Encrypt it first
    encrypt: bool = False
    # The label to use for the encrypted device; required if encrypt is True
    encrypt_label: Optional[str] = None
    # A cache of the calculated device name, internal use only
    _device_cache: Optional[str] = None

    def __post_init__(self):
        if self.filesystem and self.volgroup:
            raise InvalidBlockDeviceSpecError(
                f"Error processing WholeDiskSpec for device {self.device}: cannot pass both filesystem and volgroup to WholeDiskSpec"
            )
        if self.encrypt and not self.encrypt_label:
            raise InvalidBlockDeviceSpecError(
                f"Error processing WholeDiskSpec for device {self.device}: When 'encrypt' is True, must pass 'encrypt_label'"
            )

    @property
    def device(self) -> str:
        if not self._device_cache:
            if self._device.startswith("/dev/"):
                self._device_cache = self._device
            elif self._device.startswith("/sys/"):
                self._device_cache = syspath_to_device(self._device)
        return self._device_cache


@dataclass
class PartitionSpec:
    """A specification for a single partition"""

    # Either a device under /dev, or a device path under /sys
    # (See WholeDiskSpec for details)
    _device: str
    # The GPT partition label, different from filesystem label
    # This is required and must be unique.
    # If encrypt is set to True, this label will apply to the encrypted device.
    label: str
    # The start of the partition, passed directly to parted
    start: str
    # The end of the partition, passed directly to parted
    end: str
    # Format the partition with this filesystem; mutually exclusive with volgroup
    filesystem: Optional[FilesystemSpec] = None
    # Add the partition to this volume group; mutually exclusive with filesystem
    volgroup: Optional[str] = None
    # Encrypt it first
    encrypt: bool = False
    # A cache of the calculated device name, internal use only
    _device_cache: Optional[str] = None

    def __post_init__(self):
        if self.filesystem and self.volgroup:
            raise InvalidBlockDeviceSpecError(
                f"Error processing PartitionSpec for device {self._device} with label {self.label}: cannot pass both filesystem and volgroup to PartitionSpec"
            )

    @property
    def device(self) -> str:
        if not self._device_cache:
            if self._device.startswith("/dev/"):
                self._device_cache = self._device
            elif self._device.startswith("/sys/"):
                self._device_cache = syspath_to_device(self._device)
        return self._device_cache


# @dataclass
# class LvmVgSpec:
#     """A specification for an LVM volume group"""

#     name: str
#     devices: List[str]


@dataclass
class LvmLvSpec:
    """A specification for an LVM logical volume"""

    name: str
    volgroup: str
    # The size of the volume, passed directly to lvcreate
    size: str
    filesystem: Optional[FilesystemSpec]

    @property
    def device(self) -> str:
        return os.path.join("/dev/mapper", f"{self.volgroup}-{self.name}")


class NoDeviceFoundWithPartitionLabelError(Exception):
    pass


class InvalidBlockDeviceSpecError(Exception):
    pass


class MissingVolumeGroupError(Exception):
    pass


class DuplicatePartitionLabelError(Exception):
    pass


class EncryptionKeyfileNotFoundError(Exception):
    pass


class EncryptionKeyfileNotSetError(Exception):
    pass


class CouldNotFindSysPathError(Exception):
    pass


class CouldNotFindDevPathError(Exception):
    pass


def cryptsetup_open_idempotently(device: str, keyfile: str, lukslabel: str, encrypted_suffix: str = "_crypt"):
    """Use cryptsetup to open a device idempotently"""

    # If the 'device' argument is '/dev/sda', 'encdev' will be 'sda_crypt', and 'encdev_full' will be '/dev/mapper/sda_crypt'
    encdev = f"{os.path.basename(device)}{encrypted_suffix}"
    encdev_full = os.path.join("/dev/mapper", encdev)

    if os.path.exists(encdev_full):
        logger.info(f"cryptsetup_open_idempotently(): Encrypted device {encdev_full} already exists, nothing to do")
        return encdev_full

    needs_luks_format = False
    try:
        subprocess.run(
            f"cryptsetup open --type luks2 --batch-mode --key-file {keyfile} {device} {encdev}", shell=True, check=True
        )
        logger.info(f"cryptsetup_open_idempotently(): Opened encrypted device {encdev_full} without running luksFormat")
    except subprocess.CalledProcessError:
        logger.info(
            f"cryptsetup_open_idempotently(): Could not open encrypted device {encdev_full}, running luksFormat first..."
        )
        needs_luks_format = True

    if needs_luks_format:
        subprocess.run(
            f"cryptsetup luksFormat --type luks2 --batch-mode --label '{lukslabel}' {device} {keyfile}",
            shell=True,
            check=True,
        )
        logger.info(f"cryptsetup_open_idempotently(): Finished running luksFormat for {encdev_full}")
        subprocess.run(
            f"cryptsetup open --type luks2 --batch-mode --key-file {keyfile} {device} {encdev}", shell=True, check=True
        )
        logger.info(f"cryptsetup_open_idempotently(): Opened encrypted device {encdev_full} after running luksFormat")

    return encdev_full


def gptlabel2device(label: str) -> str:
    """Given a GPT partition label, return a path representing the partition device.

    Note that GPT partition labels are NOT filesystem labels made with e2label.

    Under udev, we can find this easily via /dev/disk/by-label/$LABELNAME,
    but using the mdev with Alpine's default rules, that will not exist,
    so we have to do it this way.
    """
    result = subprocess.run(f"blkid", check=True, capture_output=True)
    foundline = None
    for line in result.stdout.decode().split("\n"):
        if f' PARTLABEL="{label}" ' in line:
            foundline = line
            break
    if not foundline:
        raise NoDeviceFoundWithPartitionLabelError(f"Found no attached devices with partition label '{label}'")
    devicepath = foundline.split(":")[0]
    return devicepath


def is_mountpoint(path: str) -> bool:
    """Return true if a path is a mountpoint for a currently mounted filesystem"""
    mtpt = subprocess.run(["mountpoint", path], check=False, capture_output=True)
    return mtpt.returncode == 0


def syspath_to_device(syspath: str) -> str:
    """Given a path for a device in /sys, return the device path under /dev

    E.g., for a syspath like '/sys/devices/pci0000:00/0000:00:1f.2/ata1/host0/target0:0:0/0:0:0:0/block/sda/sda1',
    return the device path like '/dev/sda1'.

    I don't know how good of an idea this is!
    But we're gonna fucking move our cigar to the other side of our mouth and do it anyway.

    **This will only work on the final system**!
    It cannot be used when running progfiguration on another node like the psyops container.
    """

    #### General implementation notes
    #

    # There are at least two ways to do this:
    #
    # 1. By looking in {syspath}/dev, which contains the major and minor numbers,
    #    and then looking in /sys/dev/block/{major}:{minor} to find the device name.
    # 2. By looking in {syspath}/uevent, which contains (among other things)
    #    a DEVNAME value that we can prepend with /dev/ to get the path.
    #
    # The second method with DEVNAME is cleaner and faster (just one file read).
    # It works on psyopsOS systems with mdev.
    #
    # It may be worth mentioning that the first way is how lsblk works,
    # according to its man page:
    #
    #   > The lsblk needs to be able to lookup sysfs path by major:minor,
    #   > which is done done by using /sys/dev/block.
    #   > The block sysfs appeared in kernel 2.6.27 (October 2008).
    #   > In case of problem with new enough kernel check that
    #   > CONFIG_SYSFS was enabled at the time of kernel build.
    #
    # On systems with udev, we can get this in a more straightforward manner with udevadm,
    # but psyopsOS uses mdev which doesn't appear to have a similar tool.
    #
    # See also:
    # - <https://unix.stackexchange.com/questions/151812/get-device-node-by-major-minor-numbers-pair>
    # - lsblk man page

    #### Logic
    #

    # The device name may have changed; if so, we need to handle that.
    #
    # The user would have passed in something like
    #   /sys/devices/pci0000:00/0000:00:1f.2/ata1/host0/target0:0:0/0:0:0:0/block/sda
    # which they might get by running `readlink -f /sys/class/block/{device}`
    #
    # If we can find the uevent file inside that path, they passed in a complete path
    uevent = os.path.join(syspath, "uevent")
    # If they didn't, maybe they just passed in the part without the {device} at the end,
    # like '/sys/devices/.../block'
    # In this case, there should be exactly one child directory, and that's the {device}.
    if not os.path.exists(uevent):
        children = os.listdir(syspath)
        if len(children) == 1:
            uevent = os.path.join(syspath, children[0], "uevent")
    # If that didn't work, maybe the device name changed,
    # and they passed in eg '/sys/devices/.../block/sda' but now it's '.../block/sdb'.
    # In this case, there should be exactly one child directory inside our parent, and that's the {device}.
    if not os.path.exists(uevent):
        syspathpar = os.path.dirname(syspath)
        children = os.listdir(syspathpar)
        if len(children) == 1:
            uevent = os.path.join(syspathpar, children[0], "uevent")
    # If that doens't work, give up
    if not os.path.exists(uevent):
        raise CouldNotFindSysPathError(f"Could not find uevent file for syspath {syspath}")

    with open(uevent, "r") as f:
        for line in f:
            if line.startswith("DEVNAME="):
                devname = line.split("=")[1].strip()
                return os.path.join("/dev", devname)

    raise CouldNotFindDevPathError(f"Could not find device path for syspath {syspath}")
