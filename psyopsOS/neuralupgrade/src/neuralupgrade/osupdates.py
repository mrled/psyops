import datetime
import os
import platform
import shutil
import subprocess
import threading
import traceback
from typing import Optional

from neuralupgrade import logger
from neuralupgrade.coginitivedefects import MultiError
from neuralupgrade.downloader import download_update_signature
from neuralupgrade.filesystems import Filesystem, Filesystems, Mount, sides
from neuralupgrade.grub_cfg import write_grub_cfg_carefully
from neuralupgrade.update_metadata import minisign_verify, parse_trusted_comment, parse_psyopsOS_grub_info_comment


def get_system_versions(filesystems: Filesystems) -> dict:
    """Show information about the OS of the running system.

    Uses threads to speed up the process of mounting the filesystems and reading the minisig files.
    """
    booted, nonbooted = sides(filesystems)

    result = {
        booted: {
            "mountpoint": filesystems.bylabel(booted).mountpoint,
            "running": True,
            "next_boot": False,
        },
        nonbooted: {
            "mountpoint": filesystems.bylabel(nonbooted).mountpoint,
            "running": False,
            "next_boot": False,
        },
        "efisys": {
            "mountpoint": filesystems.efisys.mountpoint,
        },
        "booted": booted,
        "nonbooted": nonbooted,
    }

    def _get_os_tc(label: str):
        with filesystems.bylabel(label).mount(writable=False) as mountpoint:
            minisig_path = os.path.join(mountpoint, "psyopsOS.tar.minisig")
            try:
                info = parse_trusted_comment(sigfile=minisig_path)
            except FileNotFoundError:
                info = {"error": f"missing minisig at {minisig_path}"}
            except Exception as exc:
                info = {"error": str(exc), "minisig_path": minisig_path, "traceback": traceback.format_exc()}
        result[label] = {**result[label], **info}

    def _get_esp_info():
        with filesystems.efisys.mount(writable=False) as mountpoint:
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
                grub_cfg_info = parse_psyopsOS_grub_info_comment(file=grub_cfg_path)
            except FileNotFoundError:
                grub_cfg_info = {"error": f"missing grub.cfg at {grub_cfg_path}"}
            except Exception as exc:
                grub_cfg_info = {"error": str(exc), "grub_cfg_path": grub_cfg_path, "traceback": traceback.format_exc()}
        # TODO: currently if any keys overlap between grub_cfg_info and trusted_metadata, the latter will overwrite the former, fix?
        result["efisys"] = {**result["efisys"], **grub_cfg_info, **trusted_metadata}

    nonbooted_thread = threading.Thread(target=_get_os_tc, args=(booted,))
    nonbooted_thread.start()
    booted_thread = threading.Thread(target=_get_os_tc, args=(nonbooted,))
    booted_thread.start()
    efisys_thread = threading.Thread(target=_get_esp_info)
    efisys_thread.start()

    booted_thread.join()
    nonbooted_thread.join()
    efisys_thread.join()

    # Handle these after the threads have joined
    # I'm not sure what happens if the os tc threads and the efi thread tries to write to the same dict at the same time
    try:
        next_boot = result["efisys"]["default_boot_label"]
        result[next_boot]["next_boot"] = True
    except KeyError:
        result["error"] = "Could not determine next boot"

    return result


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


def apply_updates(
    filesystems: Filesystems,
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

    TODO: Rewrite this to use contextlib.ExitStack to manage the mounts.
    """

    mounts: dict[str, tuple[str, Mount]] = {}
    """A dictionary of name: (mountpoints, Mount).

    The name is a string like "a", "b", "nonbooted", or "efisys".
    The mountpoint is a string path.
    The Mount object is a context manager.

    About our use of the Mount context managers:
    Each Filesystem has a .mount() which returns a Mount context manager,
    which mounts the filesystem on entry and unmounts it on exit.
    We call the __enter__ and __exit__ methods of the Mount context manager manually
    and keep track of which are mounted in this dict
    so that we can mount what we need when we need,
    never mount the same filesystem more than once to avoid slowdowns,
    and unmount everything at the end.
    """

    def idempotently_mount(name: str, fs: Filesystem, writable: bool = False):
        if name not in mounts:
            mount = fs.mount(writable=writable)
            mountpoint = mount.__enter__()
            mounts[name] = (mountpoint, mount)
        return mounts[name]

    def idempotently_umount(name: str):
        if name in mounts:
            _, mount = mounts.pop(name)
            mount.__exit__(None, None, None)

    def unmount_all_returning_exceptions():
        exceptions = []
        # Make sure we aren't mutating the dict while iterating over it
        mount_names = list(mounts.keys())
        for name in mount_names:
            try:
                idempotently_umount(name)
            except Exception as exc:
                exceptions.append(exc)
        return exceptions

    # The default boot label is the partition label to use the next time the system boots (A or B).
    # When updating nonbooted, it is assumed to be the nonbooted side and cannot be passed explicitly,
    # although updating it can be skipped if no_update_default_boot_label is passed.
    # When installing a new psyopsESP on a partition without a grub.cfg file, it must be passed explicitly.
    # When updating an existing psyopsESP, it may be omitted to read the existing value from the existing grub.cfg file,
    # or passed explicitly.
    # When updating a or b, it will be omitted unless passed explicitly.
    # If it is passed explicitly, it must be one of the A/B labels (taking into account any overrides).
    detect_existing_default_boot_label = False
    if default_boot_label:
        if default_boot_label not in [filesystems.a.label, filesystems.b.label]:
            # If default_boot_label is passed, it has to be one of theaA/B labels
            raise Exception(
                f"Invalid default boot label '{default_boot_label}', must be one of the A/B labels '{filesystems.a.label}'/'{filesystems.b.label}'"
            )
    else:
        if "efisys" in targets and "nonbooted" not in targets:
            detect_existing_default_boot_label = True

    apply_err = None
    try:
        if detect_existing_default_boot_label:
            # We need to get the default boot label from the existing grub.cfg file.
            # We mount as writable because we might need to write a new grub.cfg file later,
            # but we can't know that until we check whether what's there matches the new value.
            efisys_mountpoint, _ = idempotently_mount("efisys", filesystems.efisys, writable=True)
            if not os.path.exists(os.path.join(efisys_mountpoint, "grub", "grub.cfg")):
                raise Exception(
                    f"--default-boot-label not passed and no existing GRUB configuration found at {efisys_mountpoint}/grub/grub.cfg file; if the ESP is empty, you need to pass --default-boot-label"
                )
            try:
                grub_cfg_info = parse_psyopsOS_grub_info_comment(
                    file=os.path.join(efisys_mountpoint, "grub", "grub.cfg")
                )
                default_boot_label = grub_cfg_info["default_boot_label"]
            except FileNotFoundError:
                default_boot_label = filesystems.a.label
            except Exception as exc:
                raise Exception(
                    f"Could not find default boot label from existing {efisys_mountpoint}/grub/grub.cfg file"
                ) from exc

        # Handle actions
        if "nonbooted" in targets:
            targets.remove("nonbooted")
            updated = datetime.datetime.now()
            booted, nonbooted = sides(filesystems)
            nonbooted_mountpoint, _ = idempotently_mount("nonbooted", filesystems.bylabel(nonbooted), writable=True)
            apply_ostar(ostar, nonbooted_mountpoint, verify=verify, verify_pubkey=pubkey)
            subprocess.run(["sync"], check=True)
            idempotently_umount("nonbooted")
            logger.info(f"Updated nonbooted side {nonbooted} with {ostar} at {nonbooted_mountpoint}")
            if not no_update_default_boot_label:
                default_boot_label = nonbooted

        for side in ["a", "b"]:
            if side in targets:
                targets.remove(side)
                this_ab_mountpoint, _ = idempotently_mount(side, filesystems[side], writable=True)
                apply_ostar(ostar, this_ab_mountpoint, verify=verify, verify_pubkey=pubkey)
                subprocess.run(["sync"], check=True)
                idempotently_umount(side)
                logger.info(f"Updated {side} side with {ostar} at {this_ab_mountpoint}")

        if "efisys" in targets:
            targets.remove("efisys")
            efisys_mountpoint, _ = idempotently_mount("efisys", filesystems.efisys, writable=True)
            # This handles any updates to the default_boot_label in grub.cfg.
            configure_efisys(
                filesystems, efisys_mountpoint, default_boot_label, tarball=esptar, verify=verify, verify_pubkey=pubkey
            )
            subprocess.run(["sync"], check=True)
            logger.info(f"Updated efisys with {esptar} at {efisys_mountpoint}")
        elif default_boot_label:
            # If we didn't handle updates to default_boot_label in grub.cfg above, do so here.
            efisys_mountpoint, _ = idempotently_mount("efisys", filesystems.efisys, writable=True)
            write_grub_cfg_carefully(filesystems, efisys_mountpoint, default_boot_label, updated=updated)
            subprocess.run(["sync"], check=True)
            logger.info(f"Updated GRUB default boot label to {default_boot_label} at {efisys_mountpoint}")

        if targets:
            raise Exception(f"Unknown targets argument(s): {targets}")

    except Exception as exc:
        apply_err = exc

    finally:
        umount_errs = unmount_all_returning_exceptions()
        if umount_errs:
            multierr_msg = (
                f"Encountered error(s) exiting mount context managers for {filesystems} with targets {targets}"
            )
            if apply_err:
                raise MultiError(multierr_msg, umount_errs) from apply_err
            raise MultiError(multierr_msg, umount_errs)
        elif apply_err:
            raise apply_err


def check_updates(
    filesystems: Filesystems,
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

    system_versions = get_system_versions(filesystems)
    esp_version = update_version
    os_version = update_version
    if update_version == "latest":
        if "a" in targets or "b" in targets or "nonbooted" in targets or "booted" in targets:
            os_latest_sig = download_update_signature(repository, psyopsOS_filename_format, architecture, "latest")
            os_version = os_latest_sig.unverified_metadata["version"]
        if "efisys" in targets:
            esp_latest_sig = download_update_signature(repository, psyopsESP_filename_format, architecture, "latest")
            esp_version = esp_latest_sig.unverified_metadata["version"]

    result = {}
    for updatetype in targets:
        if updatetype in ["a", "b", "nonbooted", "booted"]:
            if updatetype in ["nonbooted", "booted"]:
                filesystem = filesystems.bylabel(system_versions[updatetype])
            elif updatetype in ["a", "b"]:
                filesystem = filesystems[updatetype]
            else:
                raise ValueError(f"Unknown updatetype {updatetype}")
            current_version = system_versions[filesystem.label].get("version", "UNKNOWN")
            compared_to = os_version
        elif updatetype in ["efisys"]:
            filesystem = filesystems.efisys
            current_version = system_versions["efisys"].get("version", "UNKNOWN")
            compared_to = esp_version
        else:
            raise ValueError(f"Unknown updatetype {updatetype}")
        up_to_date = compared_to == current_version
        result[updatetype] = {
            "label": filesystem.label,
            "mountpoint": filesystem.mountpoint,
            "current_version": current_version,
            "compared_to": compared_to,
            "up_to_date": up_to_date,
        }

    return result
