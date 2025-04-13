"""GRUB bootloader"""

import datetime
import os
import platform
import shutil
import subprocess
import traceback
from typing import Optional

from neuralupgrade import logger
from neuralupgrade.firmware import Firmware
from neuralupgrade.firmware.uefipc.grub_cfg import write_grub_cfg_carefully
from neuralupgrade.filesystems import Filesystems
from neuralupgrade.systemmetadata import NeuralPartitionFirmware
from neuralupgrade.update_metadata import (
    minisign_verify,
    parse_psyopsOS_neuralupgrade_info_comment,
    parse_trusted_comment,
    read_default_boot_label,
)


class UEFIPCGrubBootloader(Firmware):

    fwtype = "x86_64_uefi"

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
        configure_efisys(
            filesystems=filesystems,
            efisys=efisys,
            default_boot_label=default_boot_label,
            tarball=tarball,
            verify=verify,
            verify_pubkey=verify_pubkey,
        )

    def read_default_boot_label(self, fw_mountpoint: str) -> str:
        """Read the default boot label from the bootloader configuration."""
        return read_default_boot_label(os.path.join(fw_mountpoint, "grub", "grub.cfg"))

    def write_default_boot_label(self, filesystems: Filesystems, label: str):
        """Write the default boot label to the bootloader configuration."""
        write_grub_cfg_carefully(filesystems, filesystems.efisys.mountpoint, label)
        logger.info(f"Updated GRUB default boot label to {label} at {filesystems.efisys.mountpoint}")

    def get_partition_metadata(self, filesystems: Filesystems) -> NeuralPartitionFirmware:
        """Get the firmware partition metadata."""
        return get_efi_partition_metadata(filesystems)


# Note to self: we release efisys tarballs containing stuff like memtest, which can be extracted on top of an efisys that has grub-install already run on it
def configure_efisys(
    filesystems: Filesystems,
    efisys: str,
    default_boot_label: str,
    tarball: Optional[str] = None,
    verify: bool = True,
    verify_pubkey: Optional[str] = None,
):
    """Populate the EFI system partition with the necessary files"""

    updated = datetime.datetime.now()

    machine = platform.machine()
    if machine == "x86_64":
        target = "x86_64-efi"
    else:
        raise Exception(f"Unsupported machine type {machine} for efisys configuration")

    # I don't understand why I need --boot-directory too, but I do
    cmd = [
        "grub-install",
        f"--target={target}",
        f"--efi-directory={efisys}",
        f"--boot-directory={efisys}",
        "--removable",
    ]
    logger.debug(f"Running grub-install: {cmd}")
    grub_result = subprocess.run(cmd, capture_output=True, text=True)
    grub_stderr = grub_result.stderr.strip()
    grub_stdout = grub_result.stdout.strip()
    if grub_result.returncode != 0:
        raise Exception(
            f"grub-install returned non-zero exit code {grub_result.returncode} with stdout '{grub_stdout}' and stderr '{grub_stderr}'"
        )
    logger.debug(f"grub-install stdout: {grub_stdout}")
    logger.debug(f"grub-install stderr: {grub_stderr}")

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
    subprocess.run(["sync"], check=True)

    write_grub_cfg_carefully(filesystems, efisys, default_boot_label)
    logger.debug("Done configuring efisys")


def get_efi_partition_metadata(filesystems: Filesystems) -> NeuralPartitionFirmware:
    """Read the firmware partition metadata from the minisig and boot configuration files."""
    fs = filesystems.efisys
    with fs.mount(writable=False) as mountpoint:
        minisig_path = os.path.join(mountpoint, "psyopsESP.tar.minisig")
        try:
            trusted_metadata = parse_trusted_comment(sigfile=minisig_path)
        except FileNotFoundError:
            trusted_metadata = {"error": f"missing minisig at {minisig_path}"}
        except Exception as exc:
            trusted_metadata = {
                "error": str(exc),
                "minisig_path": minisig_path,
                "traceback": traceback.format_exc(),
            }
        grub_cfg_path = os.path.join(mountpoint, "grub", "grub.cfg")
        try:
            grub_cfg_info = parse_psyopsOS_neuralupgrade_info_comment(file=grub_cfg_path)
        except FileNotFoundError:
            grub_cfg_info = {"error": f"missing grub.cfg at {grub_cfg_path}"}
        except Exception as exc:
            grub_cfg_info = {"error": str(exc), "grub_cfg_path": grub_cfg_path, "traceback": traceback.format_exc()}
    return NeuralPartitionFirmware(
        fs=fs,
        metadata=trusted_metadata,
        neuralupgrade_info=grub_cfg_info,
    )
