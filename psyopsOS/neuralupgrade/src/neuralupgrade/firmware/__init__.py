"""Bootloaders"""

import os
import shutil
import subprocess
from typing import Optional
from venv import logger
from neuralupgrade.filesystems import Filesystems
from neuralupgrade.systemmetadata import NeuralPartitionFirmware
from neuralupgrade.update_metadata import minisign_verify


class Firmware:
    """Base class for firmware / bootloaders."""

    # TODO: add an initializer with filesystems

    fwtype: str
    """This must match the platform name according to telekinesis"""

    @property
    def architecture(self) -> str:
        """The architecture of the firmware"""
        return self.fwtype.split("-")[0]

    @property
    def bootsystem(self) -> str:
        """The boot system of the firmware"""
        return self.fwtype.split("-")[1]

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
        raise NotImplementedError("Subclasses must implement this method.")

    def read_default_boot_label(self, fw_mountpoint: str) -> str:
        """Read the default boot label from the bootloader configuration."""
        raise NotImplementedError("Subclasses must implement this method.")

    def write_default_boot_label(self, filesystems: Filesystems, label: str):
        """Write the default boot label to the bootloader configuration."""
        raise NotImplementedError("Subclasses must implement this method.")

    def get_partition_metadata(self, filesystems: Filesystems) -> NeuralPartitionFirmware:
        """Get the firmware partition metadata."""
        raise NotImplementedError("Subclasses must implement this method.")

    def apply_tarball(
        self, efisys: str, tarball: Optional[str] = None, verify: bool = True, verify_pubkey: Optional[str] = None
    ):
        """Helper function that extracts tarball to the firmware partition.

        It might contain extra EFI programs like memtest,
        boot programs like U-Boot,
        firmware like Raspberry Pi start4.elf,
        etc.

        Subclasses should call this function in update() if appropriate.
        """
        if tarball:
            if verify:
                minisign_verify(tarball, pubkey=verify_pubkey)
            logger.debug(f"Extracting efisys tarball {tarball} to {efisys}")
            subprocess.run(
                [
                    "tar",
                    # Ignore permissions as we're extracting to a FAT32 filesystem
                    "--no-same-owner",
                    "--no-same-permissions",
                    "--no-overwrite-dir",
                    "-x",
                    "-f",
                    tarball,
                    "-C",
                    efisys,
                ],
                check=True,
            )
            logger.debug(f"Finished extracting {tarball} to {efisys}")
            minisig = tarball + ".minisig"
            try:
                shutil.copy(minisig, os.path.join(efisys, "psyopsESP.tar.minisig"))
                logger.debug(f"Copied {minisig} to {efisys}/psyopsESP.tar.minisig")
            except FileNotFoundError:
                logger.warning(f"Could not find {minisig}, partition will not know its version")
