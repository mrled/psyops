import contextlib
import datetime
import os
import platform
import shutil
import subprocess
import traceback
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass
from typing import Any, Optional, TypedDict

from neuralupgrade import logger
from neuralupgrade.dictify import Dictifiable
from neuralupgrade.downloader import download_update_signature
from neuralupgrade.filesystems import Filesystem, Filesystems, Sides
from neuralupgrade.grub_cfg import write_grub_cfg_carefully
from neuralupgrade.update_metadata import (
    minisign_verify,
    parse_trusted_comment,
    parse_psyopsOS_neuralupgrade_info_comment,
)


@dataclass
class NeuralPartition:
    """A managed partition for either psyopsOS or firmware"""

    fs: Filesystem
    metadata: dict[str, str]


@dataclass
class NeuralPartitionOS(NeuralPartition):
    """Result of a psyops partition operation."""

    fs: Filesystem
    metadata: dict[str, str]
    running: bool
    next_boot: bool


@dataclass
class NeuralPartitionFirmware(NeuralPartition):
    """Result of a psyopsESP operation."""

    fs: Filesystem
    metadata: dict[str, str]
    neuralupgrade_info: dict[str, str]


@dataclass
class SystemMetadata:
    """Result of a system metadata operation."""

    a: NeuralPartitionOS
    b: NeuralPartitionOS
    firmware: NeuralPartitionFirmware
    booted_label: str
    nonbooted_label: str
    nextboot_label: str

    @property
    def by_label(self) -> dict[str, NeuralPartitionOS]:
        """Return the A and B partitions by label."""
        return {self.a.fs.label: self.a, self.b.fs.label: self.b}

    @property
    def booted(self):
        """Return the booted partition."""
        return self.by_label[self.booted_label]

    @property
    def nonbooted(self):
        """Return the nonbooted partition."""
        return self.by_label[self.nonbooted_label]

    @property
    def nextboot(self):
        """Return the nextboot partition."""
        return self.by_label[self.nextboot_label]


def get_psyops_partition_metadata(fs: Filesystem) -> NeuralPartitionOS:
    """Read the psyopsOS partition metadata from the minisig file."""
    with fs.mount(writable=False) as mountpoint:
        minisig_path = os.path.join(mountpoint, "psyopsOS.tar.minisig")
        try:
            info: dict[str, Any] = {
                "running": False,
                "next_boot": False,
                **parse_trusted_comment(sigfile=minisig_path),
            }
        except FileNotFoundError:
            info = {"error": f"missing minisig at {minisig_path}"}
        except Exception as exc:
            info = {"error": str(exc), "minisig_path": minisig_path, "traceback": traceback.format_exc()}
    return NeuralPartitionOS(
        fs=fs,
        running=False,
        next_boot=False,
        metadata=info,
    )


def get_efi_partition_metadata(fs: Filesystem) -> NeuralPartitionFirmware:
    """Read the psyopsESP partition metadata from the minisig and grub_cfg files."""
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


def get_system_metadata(filesystems: Filesystems, sides: Sides) -> SystemMetadata:
    """Show information about the OS of the running system.

    Uses threads to speed up the process of mounting the filesystems and reading the minisig files.
    """
    result: dict[str, Any] = {}
    with ThreadPoolExecutor() as executor:
        future_map: dict[Future[Any], str] = {
            executor.submit(get_psyops_partition_metadata, filesystems.a): "a",
            executor.submit(get_psyops_partition_metadata, filesystems.b): "b",
            executor.submit(get_efi_partition_metadata, filesystems.efisys): "firmware",
        }

        # Collect the results from the futures
        for future in as_completed(future_map):
            label = future_map[future]
            result[label] = future.result()

    return SystemMetadata(
        a=result["a"],
        b=result["b"],
        firmware=result["firmware"],
        booted_label=sides.booted,
        nonbooted_label=sides.nonbooted,
        nextboot_label=result["firmware"].neuralupgrade_info["default_boot_label"],
    )


def apply_ostar(tarball: str, osmount: str, verify: bool = True, verify_pubkey: Optional[str] = None):
    """Apply an ostar to a device"""

    if verify:
        minisign_verify(tarball, pubkey=verify_pubkey)

    cmd = ["tar", "-x", "-f", tarball, "-C", osmount]
    logger.debug(f"Extracting {tarball} to {osmount} with {cmd}")
    subprocess.run(cmd, check=True)
    minisig = tarball + ".minisig"
    try:
        shutil.copy(minisig, os.path.join(osmount, "psyopsOS.tar.minisig"))
        logger.debug(f"Copied {minisig} to {osmount}/psyopsOS.tar.minisig")
    except FileNotFoundError:
        logger.warning(f"Could not find {minisig}, partition will not know its version")
    subprocess.run(["sync"], check=True)
    logger.debug(f"Finished applying {tarball} to {osmount}")


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


def read_default_boot_label(efisys_mountpoint: str) -> str:
    """Read the default bootlabel from a grub.cfg file"""

    try:
        grub_cfg_info = parse_psyopsOS_neuralupgrade_info_comment(
            file=os.path.join(efisys_mountpoint, "grub", "grub.cfg")
        )
        return grub_cfg_info["default_boot_label"]
    except FileNotFoundError as exc:
        raise Exception(
            f"--default-boot-label not passed and no existing GRUB configuration found at {efisys_mountpoint}/grub/grub.cfg file; if the ESP is empty, you need to pass --default-boot-label"
        ) from exc
    except Exception as exc:
        raise Exception(
            f"Could not find default boot label from existing {efisys_mountpoint}/grub/grub.cfg file"
        ) from exc


def apply_updates(
    filesystems: Filesystems,
    sides: Sides,
    targets: list[str],
    ostar: str = "",
    esptar: str = "",
    verify: bool = True,
    pubkey: str = "",
    no_update_default_boot_label: bool = False,
    default_boot_label: str = "",
):
    """Apply updates to the filesystems.

    Handles any valid combination of updates to the a, b, nonbooted, and efisys filesystems.
    Properly ensures filesystems are mounted at most once,
    and at the end tries to return them to their original state.
    (See the Mount context manager for more details on how this works.)
    """

    # The default boot label is the partition label to use the next time the system boots (A or B).
    # When updating nonbooted, it is assumed to be the nonbooted side and cannot be passed explicitly,
    # although updating it can be skipped if no_update_default_boot_label is passed.
    # When installing a new psyopsESP on a partition without a grub.cfg file, it must be passed explicitly.
    # When updating an existing psyopsESP, it may be omitted to read the existing value from the existing grub.cfg file,
    # or passed explicitly.
    # When updating a or b, it will be omitted unless passed explicitly.
    # If it is passed explicitly, it must be one of the A/B labels (taking into account any overrides).
    detect_existing_default_boot_label = not default_boot_label and "efisys" in targets and "nonbooted" not in targets

    apply_err = None
    with contextlib.ExitStack() as stack:

        # Keep track of mounted filesystems using label -> Filesystem mapping
        mounted_points: dict[str, Filesystem] = {}

        def idempotently_mount(fs: Filesystem, writable: bool = False):
            """Use a filesystem's mount context manager to mount it.

            Register the Mount context manager with the ExitStack to ensure it gets unmounted at the end.
            """
            if fs.label not in mounted_points:
                mountctx = fs.mount(writable=writable)
                stack.enter_context(mountctx)
                mounted_points[fs.label] = fs
            return mounted_points[fs.label]

        try:
            if detect_existing_default_boot_label:
                # We need to get the default boot label from the existing grub.cfg file.
                # We mount as writable because we might need to write a new grub.cfg file later,
                # but we can't know that until we check whether what's there matches the new value.
                idempotently_mount(filesystems.efisys, writable=True)
                default_boot_label = read_default_boot_label(filesystems.efisys.mountpoint)
                # Sanity check the default boot label: it must be one of the A/B labels.
                if default_boot_label not in [filesystems.a.label, filesystems.b.label]:
                    raise Exception(
                        f"Invalid default boot label '{default_boot_label}', must be one of the A/B labels '{filesystems.a.label}'/'{filesystems.b.label}'"
                    )

            # Handle actions
            updated = None
            if "nonbooted" in targets:
                targets.remove("nonbooted")
                updated = datetime.datetime.now()
                nonbooted_fs = idempotently_mount(filesystems.bylabel(sides.nonbooted), writable=True)
                apply_ostar(ostar, nonbooted_fs.mountpoint, verify=verify, verify_pubkey=pubkey)
                subprocess.run(["sync"], check=True)
                logger.info(f"Updated nonbooted side {sides.nonbooted} with {ostar} at {nonbooted_fs}")
                if not no_update_default_boot_label:
                    default_boot_label = sides.nonbooted

                # If we specified "nonbooted" AND "a", and a is the nonbooted side,
                # remove "a" from the targets list since we just updated it.
                if sides.nonbooted in targets:
                    targets.remove(sides.nonbooted)

            for side in ["a", "b"]:
                if side in targets:
                    targets.remove(side)
                    this_fs = idempotently_mount(filesystems[side], writable=True)
                    apply_ostar(ostar, this_fs.mountpoint, verify=verify, verify_pubkey=pubkey)
                    subprocess.run(["sync"], check=True)
                    logger.info(f"Updated {side} side with {ostar} at {this_fs.mountpoint}")

            if "efisys" in targets:
                targets.remove("efisys")
                efisys_fs = idempotently_mount(filesystems.efisys, writable=True)
                # This handles any updates to the default_boot_label in grub.cfg.
                configure_efisys(
                    filesystems,
                    efisys_fs.mountpoint,
                    default_boot_label,
                    tarball=esptar,
                    verify=verify,
                    verify_pubkey=pubkey,
                )
                subprocess.run(["sync"], check=True)
                logger.info(f"Updated efisys with {esptar} at {efisys_fs}")
            elif default_boot_label:
                # If we didn't handle updates to default_boot_label in grub.cfg above, do so here.
                efisys_fs = idempotently_mount(filesystems.efisys, writable=True)
                write_grub_cfg_carefully(filesystems, efisys_fs.mountpoint, default_boot_label, updated=updated)
                subprocess.run(["sync"], check=True)
                logger.info(f"Updated GRUB default boot label to {default_boot_label} at {efisys_fs}")

            if targets:
                raise Exception(f"Unknown targets argument(s): {targets}")

        except Exception as exc:
            apply_err = exc

    # After the ExitStack exits, all mounts will have been unmounted
    # If we had an error during the update process, re-raise it
    if apply_err:
        raise apply_err


def check_updates(
    filesystems: Filesystems,
    sides: Sides,
    targets: list[str],
    update_version: str,
    repository: str,
    psyopsOS_filename_format: str,
    psyopsESP_filename_format: str,
    architecture: str,
) -> dict[str, dict[str, str]]:
    """Check if the system is up to date.

    Return a dictionary where the keys are the targets and the values are dictionaries with the following keys:
    - label: The label of the filesystem
    - mountpoint: The mountpoint of the filesystem
    - current_version: The current version of the filesystem
    - compared_to: The version to compare to
    - up_to_date: Whether the filesystem is up to date
    """

    system_md = get_system_metadata(filesystems, sides)
    update_version_firmware = update_version
    update_version_os = update_version
    if update_version == "latest":
        if "a" in targets or "b" in targets or "nonbooted" in targets or "booted" in targets:
            os_latest_sig = download_update_signature(repository, psyopsOS_filename_format, architecture, "latest")
            update_version_os = os_latest_sig.unverified_metadata["version"]
        if "efisys" in targets:
            esp_latest_sig = download_update_signature(repository, psyopsESP_filename_format, architecture, "latest")
            update_version_firmware = esp_latest_sig.unverified_metadata["version"]

    result = {}
    current_version_os = system_md.booted.metadata.get("version", "UNKNOWN")
    current_version_firmware = system_md.firmware.metadata.get("version", "UNKNOWN")
    md: NeuralPartition
    for updatetype in targets:
        if updatetype in ["a", "b", "nonbooted", "booted"]:
            if updatetype == "a":
                md = system_md.a
            elif updatetype == "b":
                md = system_md.b
            elif updatetype == "booted":
                md = system_md.booted
            elif updatetype == "nonbooted":
                md = system_md.nonbooted
            result[updatetype] = {
                "label": md.fs.label,
                "mountpoint": md.fs.mountpoint,
                "current_version": current_version_os,
                "compared_to": update_version_os,
                "up_to_date": update_version_os == current_version_os,
            }
        elif updatetype == "efisys":
            md = system_md.firmware
            result[updatetype] = {
                "label": md.fs.label,
                "mountpoint": md.fs.mountpoint,
                "current_version": current_version_firmware,
                "compared_to": update_version_firmware,
                "up_to_date": update_version_firmware == current_version_firmware,
            }
        else:
            raise ValueError(f"Unknown updatetype {updatetype}")

    return result
