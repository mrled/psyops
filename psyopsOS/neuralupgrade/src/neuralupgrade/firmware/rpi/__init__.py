import datetime
import glob
import os
import shutil
import traceback
from typing import Optional
from venv import logger
from neuralupgrade.filesystems import Filesystems
from neuralupgrade.firmware import Firmware
from neuralupgrade.firmware.rpi.rpi_cfg import write_rpi_cfgs_carefully
from neuralupgrade.systemmetadata import NeuralPartitionFirmware
from neuralupgrade.update_metadata import (
    parse_psyopsOS_neuralupgrade_info_comment,
    read_default_boot_label,
)


class RaspberryPiUBootBootloader(Firmware):
    """Base class for firmware / bootloaders."""

    fwtype = "raspberrypi"

    def update(
        self,
        filesystems: Filesystems,
        efisys: str,
        default_boot_label: str,
        tarball: Optional[str] = None,
        verify: bool = True,
        verify_pubkey: Optional[str] = None,
    ):
        """Update the bootloader configuration."""
        return install_rpi_uboot(
            filesystems,
            efisys,
            default_boot_label,
            tarball=tarball,
            verify=verify,
            verify_pubkey=verify_pubkey,
        )

    def read_default_boot_label(self, fw_mountpoint: str) -> str:
        """Read the default boot label from the bootloader configuration."""
        return read_default_boot_label(os.path.join(fw_mountpoint, "boot.cmd"))

    def write_default_boot_label(self, filesystems: Filesystems, label: str):
        """Write the default boot label to the bootloader configuration."""
        write_rpi_cfgs_carefully(filesystems, filesystems.efisys.mountpoint, label)
        logger.info(f"Updated GRUB default boot label to {label} at {filesystems.efisys.mountpoint}")

    def get_partition_metadata(self, filesystems: Filesystems) -> NeuralPartitionFirmware:
        """Get the firmware partition metadata."""
        return get_rpi_partition_metadata(filesystems)


def install_rpi_uboot(
    filesystems: Filesystems,
    efisys: str,
    default_boot_label: str,
    tarball: Optional[str] = None,
    verify: bool = True,
    verify_pubkey: Optional[str] = None,
):
    """Populate the Raspberry Pi boot partition with the necessary files

    Expects to be run from an Alpine system for the ARM architecture with the following packages installed:
    - u-boot-raspberrypi: Contains the U-Boot binary that we copy to the boot partition
    - uboot-tools: Contains the mkimage tool that we use to create the U-Boot image
    - raspberrypi-bootloader: Contains the bootloader files that we copy to the boot partition

    Currently we don't support any extra programs or a tarbarll for Raspberry Pi systems,
    so the tarball, verify, and verify_pubkey options are ignored.
    """
    updated = datetime.datetime.now()
    for f in [
        # U-Boot itself, from u-boot-raspberrypi package
        "/usr/share/u-boot/rpi_arm64/u-boot.bin",
        # Raspberry Pi firmware, from raspberrypi-bootloader package
        "/boot/start4.elf",
        "/boot/fixup4.dat",
    ]:
        shutil.copy(f, os.path.join(efisys, os.path.basename(f)))

    # The relevant DTB is surprisingly REQUIRED for U-Boot, BEFORE the kernel loads.
    # If it isn't present, U-Boot will not work at all, will not attempt to run its boot.scr file, anything.
    # It must be present in the root of the boot partition.
    # The overlays are also required for U-Boot --
    # at least, the disable-bt overly must be present (and dtoverlay=disable-bt in config.txt)
    # for the kernel to use the serial port after it boots.
    # WARNING: I am not sure what happens if the U-Boot dtb and dtbo are different from the kernel dtb and dtbo.
    for dtb in glob.glob("/boot/*.dtb"):
        shutil.copy(dtb, os.path.join(efisys, os.path.basename(dtb)))
    dst_overlays = os.path.join(efisys, "overlays")
    os.makedirs(dst_overlays, exist_ok=True)
    for dtbo in glob.glob("/boot/overlays/*.dtbo"):
        shutil.copy(dtbo, os.path.join(dst_overlays, os.path.basename(dtbo)))

    write_rpi_cfgs_carefully(filesystems, efisys, default_boot_label, updated)
    logger.debug("Done configuring U-Boot for Raspberry Pi")


def get_rpi_partition_metadata(filesystems: Filesystems) -> NeuralPartitionFirmware:
    """Read the firmware partition metadata from the minisig and boot configuration files."""

    with filesystems.efisys.mount(writable=False) as mountpoint:
        boot_cmd_path = os.path.join(mountpoint, "boot.cmd")
        try:
            boot_cmd_info = parse_psyopsOS_neuralupgrade_info_comment(file=boot_cmd_path)
        except FileNotFoundError:
            boot_cmd_info = {"error": f"missing boot.cmd at {boot_cmd_path}"}
        except Exception as exc:
            boot_cmd_info = {
                "error": str(exc),
                "boot_cmd_path": boot_cmd_path,
                "traceback": traceback.format_exc(),
            }
    return NeuralPartitionFirmware(
        fs=filesystems.efisys,
        # For U-Boot we don't have any extra programs we distribute so there is no minisig metadata
        metadata={},
        neuralupgrade_info=boot_cmd_info,
    )
