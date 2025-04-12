"""Bootloaders"""

from typing import Optional
from neuralupgrade.filesystems import Filesystems
from neuralupgrade.systemmetadata import NeuralPartitionFirmware


class Firmware:
    """Base class for firmware / bootloaders."""

    fwtype: str

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
