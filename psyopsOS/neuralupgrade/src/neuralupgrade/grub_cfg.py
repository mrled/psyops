"""The grub.cfg file for psyopsOS."""

import datetime
import glob
import json
import os
import shutil
import subprocess
from typing import Optional

from neuralupgrade import logger
from neuralupgrade.filesystems import Filesystems


# These are format strings -- literal { and } must be escaped as {{ and }}

_header_format = """\
# psyopsOS grub.cfg
# This file is generated by neuralupgrade and will be overwritten on the next update.

#### The next line is used by neuralupgrade to show information about the current configuration.
# neuralupgrade-info: last_updated={last_updated} default_boot_label={default_boot_label} extra_programs={extra_programs}
####

# Should be one of the labels defined below
set default="{default_boot_label}"

set timeout=5

insmod all_video
set gfxmode=auto
serial --speed=115200 --unit=0 --word=8 --parity=no --stop=1
terminal_input console serial
terminal_output console serial

# This is slow and uselessly verbose
#set debug=all

menuentry "Welcome to psyopsOS. GRUB configuration last updated: {last_updated}" {{
    echo "Welcome to psyopsOS. GRUB configuration last updated: {last_updated}"
}}
menuentry "----------------------------------------" {{
    echo "----------------------------------------"
}}
"""

_footer_format = """\
menuentry "UEFI fwsetup" {{
    fwsetup
}}

menuentry "Reboot" {{
    reboot
}}

menuentry "Poweroff" {{
    halt
}}

menuentry "Exit GRUB" {{
    exit
}}
"""

_psyopsOS_entry_format = """\
menuentry "{label}" {{
    search --no-floppy --label {label} --set root
    linux /kernel ro psyopsos={label} {kernel_params}
    initrd /initramfs
}}
"""

_efiprogram_entry_format = """\
menuentry "{entry_name}" {{
    insmod part_gpt
    insmod fat
    insmod chain
    search --no-floppy --label {label_efisys} --set root
    chainloader {binary_path}
}}
"""


def grub_cfg(
    filesystems: Filesystems,
    default_boot_label: str,
    extra_programs: dict[str, str],
    updated: Optional[datetime.datetime] = None,
    kernel_params_append: str = "",
    # The following are not meant to be changed normally
    kernel_params_base: str = "earlyprintk=dbgp console=tty0 console=ttyS0,115200",
) -> str:
    """Return a grub.cfg file for psyopsOS.

    Arguments
    default_boot_label:     The label of the default boot entry, should be the label of the A or B filesystem.
    extra_programs:         A dictionary of additional EFI program paths to menu titles.
    updated:                The time the grub.cfg file was last updated.
                            If None, defaults to the current time.
    kernel_params_append:   Parameters to add to the base parameters.

    It is recommended not to change the following arguments, as they are used by the build/update system:
    kernel_params_base:     The kernel parameters to add to both A and B menu entries.
                            You probably don't want to change this, but use kernel_params_append instead.
                            - debug=all prints dmesg to the screen during boot, and maybe other things
                            - earlyprintk=dbgp enables early printk, which prints kernel messages to the screen during
                              boot
                            - console=tty0 and console=ttyS0,115200 enable the kernel to print messages to the screen
                              during boot; tty0 is the screen, ttyS0 is the serial port
    """
    kernel_params = f"{kernel_params_base} {kernel_params_append}".strip()
    if not updated:
        updated = datetime.datetime.now()
    sections = [
        _header_format.format(
            default_boot_label=default_boot_label,
            last_updated=updated.strftime("%Y%m%d-%H%M%S"),
            extra_programs=",".join(extra_programs.keys()),
        ),
        _psyopsOS_entry_format.format(label=filesystems.a.label, kernel_params=kernel_params),
        _psyopsOS_entry_format.format(label=filesystems.b.label, kernel_params=kernel_params),
    ]
    for binary_path, entry_name in extra_programs.items():
        sections.append(
            _efiprogram_entry_format.format(
                label_efisys=filesystems.efisys.label, binary_path=binary_path, entry_name=entry_name
            )
        )
    sections.append(_footer_format.format())

    return "\n\n".join(sections)


def read_efisys_manifest(efisys: str) -> dict:
    """Read the manifest.json file from the EFI system partition"""
    try:
        with open(os.path.join(efisys, "manifest.json")) as f:
            manifest = json.load(f)
            logger.debug(f"Found {efisys}/manifest.json: {manifest}")
            return manifest
    except FileNotFoundError:
        logger.debug(f"Could not find {efisys}/manifest.json")
        return {}


def write_grub_cfg_carefully(
    filesystems: Filesystems,
    mountpoint: str,
    default_boot_label: str,
    updated: Optional[datetime.datetime] = None,
    # The following are not meant to be changed normally
    max_old_files: int = 10,
    max_old_days: int = 30,
):
    """Write a new grub.cfg file

    - Retrieve the extra_programs from the manifest.json file
    - Write it to a temporary file
    - Move the old one to a backup location
    - Move the new one into place
    - Keep backups, but remove more than max_old_files backups that are older than max_old_days days

    We create backup files with a timestamp in the filename,
    but when we remove them we only look at the modification time.
    On FAT32, the modification time is only accurate to 2 seconds.
    Whatever.
    """
    manifest = read_efisys_manifest(mountpoint)
    logger.debug(f"Using manifest.json from {mountpoint}: {manifest}")
    extra_programs = manifest.get("extra_programs", {})
    stampfmt = "%Y%m%d-%H%M%S.%f"
    nowstamp = datetime.datetime.now().strftime(stampfmt)
    tmpfile = os.path.join(mountpoint, "grub", f"grub.cfg.new.{nowstamp}")
    grubcfg = os.path.join(mountpoint, "grub", "grub.cfg")
    grubcfg_backup = os.path.join(mountpoint, "grub", f"grub.cfg.old.{nowstamp}")

    logger.debug(f"Writing new grub.cfg to {tmpfile}")
    with open(tmpfile, "w") as f:
        f.write(grub_cfg(filesystems, default_boot_label, extra_programs, updated))

    if os.path.exists(grubcfg):
        logger.debug(f"Backing up old {grubcfg} to {grubcfg_backup}")
        shutil.copy(grubcfg, grubcfg_backup)
        subprocess.run(["sync"], check=True)
    else:
        logger.debug(f"No old {grubcfg} to back up")
    logger.debug(f"Moving new {tmpfile} to {grubcfg}")
    shutil.move(tmpfile, grubcfg)
    subprocess.run(["sync"], check=True)

    oldfiles = glob.glob(os.path.join(mountpoint, "grub", "grub.cfg.old.*"))
    for idx, oldfile in enumerate(oldfiles):
        if idx < max_old_files:
            logger.debug(f"Keeping {oldfile} because it's one of the {max_old_files} most recent")
            continue
        olddate = datetime.datetime.fromtimestamp(os.path.getmtime(oldfile))
        if (datetime.datetime.now() - olddate).days > max_old_days:
            logger.debug(
                f"Removing {oldfile} because it's older than {max_old_days} days and there are more than {max_old_files} backups"
            )
            os.remove(oldfile)
        else:
            logger.debug(f"Keeping {oldfile} because it's newer than {max_old_days} days")
    subprocess.run(["sync"], check=True)
