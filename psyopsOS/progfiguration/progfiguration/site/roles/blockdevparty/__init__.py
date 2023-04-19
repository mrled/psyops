"""Set up a data disk"""

from ast import Dict
from dataclasses import dataclass, field
import json
import os
import subprocess
from typing import List

from progfiguration import logger
from progfiguration.inventory.roles import ProgfigurationRole
from progfiguration.localhost.disks import (
    DuplicatePartitionLabelError,
    EncryptionKeyfileNotFoundError,
    EncryptionKeyfileNotSetError,
    FilesystemSpec,
    LvmLvSpec,
    MissingVolumeGroupError,
    PartitionSpec,
    WholeDiskSpec,
    cryptsetup_open_idempotently,
    gptlabel2device,
)


# TODO: write a umount script for blockdevparty
# def write_umount(
#     wholedisks: List[WholeDiskSpec],
#     partitions: List[PartitionSpec],
#     volumes: List[LvmLvSpec],
# ):
#     """Create a umount script for all the filesystems and LVM volumes we create"""

#     blockdevs = (
#         [v.filesystem for v in volumes if v.filesystem]
#         + [p.filesystem for p in partitions if p.filesystem]
#         + [d.filesystem for d in wholedisks if d.filesystem]
#     )
#     lvs = [v.name for v in volumes if v.name]
#     vgs = (
#         [v.volgroup for v in volumes if v.volgroup]
#         + [p.volgroup for p in partitions if p.volgroup]
#         + [d.volgroup for d in wholedisks if d.volgroup]
#     )


def process_disks(
    wholedisks: List[WholeDiskSpec],
    partitions: List[PartitionSpec],
    volumes: List[LvmLvSpec],
    encryption_keyfile: str,
):
    """Partition disks, format filesystems, and create logical volumes"""

    #### Pre-processing
    # Code in this section should not write anything to disk.

    if encryption_keyfile:
        if not os.path.exists(encryption_keyfile):
            raise EncryptionKeyfileNotFoundError(f"Encryption keyfile was not found at {encryption_keyfile}")

    # A dict where keys are volume group names and values are paths to group member block devices
    volgroups: Dict[str, List[str]] = {}

    # In all disks, enumerate volume/encryption data
    for disk in wholedisks:
        if disk.volgroup:
            if disk.volgroup not in volgroups:
                volgroups[disk.volgroup] = []
            volgroups[disk.volgroup] += [disk.device]
        if disk.encrypt and not encryption_keyfile:
            raise EncryptionKeyfileNotSetError(
                f"Encryption is configured for disk {disk.device}, but encryption_keyfile was not passed"
            )

    partlabels = []

    # Enumerate volgroups from partition specifications
    # At this point we don't know the partition device yet,
    # but we want to make sure that all the VGs we need will exist later.
    # We also require a label for all partitions.
    # The label must be unique across ALL disks in the system,
    # as we use it to look up a particular partition --
    # this is easier than dealing with partition numbers.
    for partition in partitions:
        if partition.volgroup and partition.volgroup not in volgroups:
            volgroups[partition.volgroup] = []
        if partition.label in partlabels:
            raise DuplicatePartitionLabelError(f"The partition label {partition.label} is not unique!")
        if partition.encrypt and not encryption_keyfile:
            raise EncryptionKeyfileNotSetError(
                f"Encryption is configured for partition with label {partition.label} on device {partition.device}, but encryption_keyfile was not passed"
            )

    # A dict where keys are volume group names and values are LvmLvSpec objects
    vglvmap: Dict[str, List[LvmLvSpec]] = {vg: [] for vg in volgroups.keys()}

    # A dict where keys are block device paths and values are FilesystemSpec objects
    filesystems: Dict[str, List[FilesystemSpec]] = {}

    # If any VG isn't going to exist when we finish processing all the partitions,
    # throw an error here before writing anything to disk.
    for lv in volumes:
        if lv.volgroup not in volgroups:
            raise MissingVolumeGroupError(f"Volume group '{lv.volgroup}' does not exist")
        vglvmap[lv.volgroup] += [lv]

    #### Finished with pre-processing
    # Code after this may make permanent changes to disk.

    # For all disks, encrypt if and/or schedule for filesystem creation
    for disk in wholedisks:
        fsdevice = disk.device
        if disk.encrypt:
            fsdevice = cryptsetup_open_idempotently(disk.device, encryption_keyfile, disk.encrypt_label)
        if disk.filesystem:
            filesystems[fsdevice] = disk.filesystem

    universal_parted_prefix = f"parted --script --json --align optimal "

    # Process "partition tables" aka "disk labels"
    # In order to add partitions to disks in the next step,
    # we need to ensure each disk has a partition table.
    for disk in set([p.device for p in partitions]):
        parted_prefix = universal_parted_prefix + f" {disk} -- "

        # 'unit s' means our units will be in sectors
        # 'print free' means print all partitions and chunks of free space
        # parted will return nonzero if this doesn't have a partition label, so we cannot check=True
        parted_cmd = parted_prefix + "unit s print free"
        result = subprocess.run(parted_cmd, shell=True, capture_output=True)
        # There must be a disk here because it was passed in explicitly
        # An empty disk will still show information;
        # no output at all should mean an error.
        if not result.stdout:
            logger.error(
                f"No result for parted command '{parted_cmd}'. stdout: '{result.stdout}'; stderr: '{result.stderr}'"
            )
            raise Exception(f"parted could not read disk {disk}")
        diskinfo = json.loads(result.stdout)

        # Ensure that the disk has a GPT partition table
        if diskinfo["disk"]["label"] == "unknown":
            logger.info(f"The device {disk} does not have a partition table")

            subprocess.run(parted_prefix + "mklabel gpt", shell=True, check=True)
            logger.info(f"Created partition table on device {disk}")

        else:
            logger.info(f"The device {disk} already has a partition table")

    # Process partitions
    for partspec in partitions:
        parted_prefix = universal_parted_prefix + f" {partspec.device} -- "

        result = subprocess.run(parted_prefix + "unit s print free", shell=True, check=True, capture_output=True)
        diskinfo = json.loads(result.stdout)

        # Find the partition if it already exists
        # We only search by label here, we don't make sure its start/end sector is correct!
        existing_partition = None
        for partition in diskinfo["disk"]["partitions"]:
            if "name" in partition and partition["name"] == partspec.label:
                existing_partition = partition
                logger.info(
                    f"Found existing partition on device {partspec.device} with label {partspec.label}, nothing to do"
                )
                break

        # Create the partition if it doesn't already exist
        if not existing_partition:
            logger.info(f"No existing partition on device {partspec.device} with label {partspec.label}, will create")

            # # We look here for the last free chunk on the disk, which we will use to create the new partition.
            # # If this actually turns out to be a partition (and not a chunk of free space), fail.
            # freechunk = diskinfo["disk"]["partitions"][-1]
            # if freechunk["type"] != "free":
            #     raise Exception(
            #         f"Cannot create partition on {partspec.device} with label {partspec.label} because the disk has no free space left"
            #     )
            # subprocess.run(
            #     parted_prefix + f"mkpart {partspec.device} {freechunk['start']} {partspec.size}",
            #     shell=True,
            #     check=True,
            # )

            # We make the user pass in explicit start/end of the partition.
            # Note that there is no protection against overlapping partitions, which will lose data!
            subprocess.run(
                parted_prefix + f"mkpart {partspec.label} {partspec.start} {partspec.end}", shell=True, check=True
            )

        else:
            logger.info(f"The partition {partspec.label} already exists on device {partspec.device}, nothing to do")

        # Encrypt the partition if specified
        devpath = gptlabel2device(partspec.label)
        if partspec.encrypt:
            devpath = cryptsetup_open_idempotently(devpath, encryption_keyfile, partspec.label)

        # Mark (optionally encrypted) partition as a member of a volume group
        if partspec.volgroup:
            volgroups[partspec.volgroup] += [devpath]

        # Mark (optionally encrypted) partition for filesystem creation
        if partspec.filesystem:
            filesystems[devpath] = partspec.filesystem

    # Process LVM groups
    for vg, devices in volgroups.items():
        # TODO: allow expanding VGs live if we add a disk
        # Currently this will require manual intervention.

        if subprocess.run(f"vgs {vg}", shell=True, check=False).returncode != 0:
            subprocess.run(f"vgcreate {vg} {' '.join(devices)}", shell=True, check=True)

        subprocess.run(f"vgchange --activate y {vg}", shell=True, check=True)

        # Process LVM volumes
        lvs_result = subprocess.run(f"lvs {vg}", shell=True, check=False, capture_output=True)
        for lv in vglvmap[vg]:
            lv: LvmLvSpec
            if lv.name not in lvs_result.stdout.decode():
                logger.info(f"Creating volume {lv.name} on vg {vg}...")
                # lvcreate is very annoying as it uses --extents for percentages and --size for absolute values
                szflag = ""
                if "%" in lv.size:
                    szflag = "-l"
                else:
                    szflag = "-L"
                subprocess.run(f"lvcreate {szflag} {lv.size} -n {lv.name} {vg}", shell=True, check=True)
            if lv.filesystem:
                filesystems[lv.device] = lv.filesystem

    # Format filesystems
    for device, fsspec in filesystems.items():
        fsspec: FilesystemSpec

        blkid_result = subprocess.run(["blkid", device], check=False, capture_output=True)
        if blkid_result.returncode == 0:
            logger.info(
                f"Found an existing filesystem on block device {device}, nothing to do. blkid output: {blkid_result.stdout}"
            )
            continue

        logger.info(f"No filesystem on block device {device}, creating...")
        mkfs = f"mkfs.{fsspec.fstype}"
        command = [mkfs, fsspec.label_flag, fsspec.label, *fsspec.options, device]
        subprocess.run(command, check=True)
        logger.info(f"Created {fsspec.fstype} filesystem on {device}")


@dataclass(kw_only=True)
class Role(ProgfigurationRole):

    wholedisks: List[WholeDiskSpec] = field(default_factory=list)
    partitions: List[PartitionSpec] = field(default_factory=list)
    volumes: List[LvmLvSpec] = field(default_factory=list)
    encryption_keyfile: str = "/mnt/psyops-secret/mount/age.key"

    def apply(self):
        """Partition disks, format filesystems, and create logical volumes

        WARNING:    It probably will not work to take a disk from an old host and add it to a new host without wiping it.
                    We look up partitions by their label, and duplicate labels will confuse this logic.
        """

        subprocess.run(
            f"apk add cryptsetup device-mapper e2fsprogs e2fsprogs-extra lvm2 parted", shell=True, check=True
        )
        subprocess.run("rc-service lvm start", shell=True, check=True)
        subprocess.run("rc-service dmcrypt start", shell=True, check=True)

        process_disks(self.wholedisks, self.partitions, self.volumes, self.encryption_keyfile)
