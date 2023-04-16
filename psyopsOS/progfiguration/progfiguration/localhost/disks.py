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

    device: str
    filesystem: Optional[FilesystemSpec] = None
    volgroup: Optional[str] = None
    encrypt: bool = False
    encrypt_label: Optional[str] = None

    def __post_init__(self):
        if self.filesystem and self.volgroup:
            raise InvalidBlockDeviceSpecError(
                f"Error processing WholeDiskSpec for device {self.device}: cannot pass both filesystem and volgroup to WholeDiskSpec"
            )
        if self.encrypt and not self.encrypt_label:
            raise InvalidBlockDeviceSpecError(
                f"Error processing WholeDiskSpec for device {self.device}: When 'encrypt' is True, must pass 'encrypt_label'"
            )


@dataclass
class PartitionSpec:
    """A specification for a single partition"""

    # The device to partition, like '/dev/sda'
    device: str
    # The GPT partition label, different from filesystem label
    # This is required and must be unique.
    # If encrypt is set to True, this label will apply to the encrypted device.
    label: str
    # The start of the partition, passed directly to parted
    start: str
    # The end of the partition, passed directly to parted
    end: str
    filesystem: Optional[FilesystemSpec] = None
    volgroup: Optional[str] = None
    encrypt: bool = False

    def __post_init__(self):
        if self.filesystem and self.volgroup:
            raise InvalidBlockDeviceSpecError(
                f"Error processing PartitionSpec for device {self.device} with label {self.label}: cannot pass both filesystem and volgroup to PartitionSpec"
            )


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


def cryptsetup_open_idempotently(device: str, keyfile: str, lukslabel: str):
    """Use cryptsetup to open a device idempotently"""

    encdev_full = os.path.join("/dev/mapper", lukslabel)

    if os.path.exists(encdev_full):
        logger.info(f"cryptsetup_open_idempotently(): Encrypted device {encdev_full} already exists, nothing to do")
        return encdev_full

    needs_luks_format = False
    try:
        subprocess.run(
            f"cryptsetup open --type luks2 --batch-mode --key-file {keyfile} {device} {lukslabel}",
            shell=True,
            check=True,
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
            f"cryptsetup open --type luks2 --batch-mode --key-file {keyfile} {device} {lukslabel}",
            shell=True,
            check=True,
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
