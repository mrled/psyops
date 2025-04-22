import datetime
import os
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


class RaspberryPi4UBootBootloader(Firmware):
    """Base class for firmware / bootloaders."""

    fwtype = "aarch64-rpi4uboot"

    def update(
        self,
        filesystems: Filesystems,
        efisys: str,
        default_boot_label: str,
        tarball: Optional[str] = None,
        verify: bool = True,
        verify_pubkey: Optional[str] = None,
    ):
        """Update the bootloader configuration.

        Needs the u-boot-tools package to be installed.
        """
        updated = datetime.datetime.now()
        write_rpi_cfgs_carefully(filesystems, efisys, default_boot_label, updated)
        self.apply_tarball(
            efisys=efisys,
            tarball=tarball,
            verify=verify,
            verify_pubkey=verify_pubkey,
        )
        logger.debug("Done configuring U-Boot for Raspberry Pi")

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
