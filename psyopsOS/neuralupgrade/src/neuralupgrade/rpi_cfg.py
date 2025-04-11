import datetime
import os
import subprocess
import tempfile
from typing import Optional

from neuralupgrade import logger
from neuralupgrade.filesystems import Filesystems
from neuralupgrade.filewriter import write_file_carefully


# A string.Template that sets variables in the boot.cmd file.
_boot_cmd_header_template = """\
# psyopsOS boot.cmd
# Variables populated by neuralupgrade

#### The next line is used by neuralupgrade to show information about the current configuration.
# neuralupgrade-info: last_updated={last_updated} default_boot_label={default_boot_label}
####

# The date this was last updated
setenv last_updated {last_updated}

# The partition labels for the A and B filesystems.
setenv psyopsOS_A_label $A_label
setenv psyopsOS_B_label $B_label

# The default boot label (must be one of A or B)
setenv default_boot_label $default_boot_label

# Starting addresses for kernel and initramfs.
# These are JUST used during boot and do not affect OS runtime;
# Linux will move itself around in memory as needed,
# and initrd is mounted to a tmpfs instance at boot,
# so the original memory buffer from U-Boot is freed.
setenv kernel_addr_r $kernel_addr_r
setenv ramdisk_addr_r $ramdisk_addr_r

# Kernel commandline parameters to each A/B side
setenv kernel_params "$kernel_params"

"""

# A string, with no variables, that uses the variables set in the header.
_boot_cmd_body = """\
# Clear previous bootmenu
for i in 0 1 2 3 4 5; do
    setenv bootmenu_${i}
done

# Probe for psyopsOS A and B partitions by their partition label.
# Currently only look on mmc and usb devices because my only U-Boot platform is the Raspberry Pi.
setenv probe_devtypes "mmc usb"
# setenv probe_devtypes "mmc usb sata scsi"

setenv psyopsOS_A_devtype ""
setenv psyopsOS_A_devnum ""
setenv psyopsOS_A_partnum ""
setenv psyopsOS_B_devtype ""
setenv psyopsOS_B_devnum ""
setenv psyopsOS_B_partnum ""
for devtype in ${devtypes}; do
    for devnum in 0 1 2; do
        if ${devtype} dev ${devnum}; then
            for partnum in 1 2 3 4 5 6 7 8; do
                if part uuid ${devtype} ${devnum}:${partnum} uuid; then
                    blkid uuid ${uuid} label
                    if test "${label}" = "${psyopsOS_A_label}"; then
                        # echo "Found ${psyopsOS_A_label} on ${devtype} ${devnum}:${partnum}"
                        setenv psyopsOS_A_devtype ${devtype}
                        setenv psyopsOS_A_devnum ${devnum}
                        setenv psyopsOS_A_partnum ${partnum}
                    elif test "${label}" = "${psyopsOS_B_label}"; then
                        # echo "Found ${psyopsOS_B_label} on ${devtype} ${devnum}:${partnum}"
                        setenv psyopsOS_B_devtype ${devtype}
                        setenv psyopsOS_B_devnum ${devnum}
                        setenv psyopsOS_B_partnum ${partnum}
                    fi
                fi
            done
        fi
    done
done

# Exit with an error if it can't find anything to boot
if test "${psyopsOS_A_devtype}" == "" && "${psyopsOS_B_devtype}" == ""; then
    echo "ERROR: No psyopsOS partitions found!"
    # Drop into the U-Boot shell
    exit
fi

echo "Welcome to psyopsOS. U-Boot configuration last updated: {last_updated}"
echo "----------------------------------------"

# Fallback error message if default_boot_label is not found
setenv default_bootcmd "echo "ERROR: Default boot label ${default_boot_label} not found! Exiting to U-Boot shell..."; exit;"

# Boot commands for each label
setenv menu_index 0
if test "${psyopsOS_A_devtype}" != ""; then
    setenv bootmenu_${menu_index} "${psyopsOS_A_label}=run boot_psyopsOS_A"
    if test "${default_boot_label}" = "${psyopsOS_A_label}"; then
        setenv default_bootcmd "run boot_psyopsOS_A"
    fi
    setexpr menu_index ${menu_index} + 1
fi
if test "${psyopsOS_B_devtype}" != ""; then
    setenv bootmenu_${menu_index} "${psyopsOS_B_label}=run "
    if test "${default_boot_label}" = "${psyopsOS_B_label}"; then
        setenv default_bootcmd "run boot_psyopsOS_B"
    fi
    setexpr menu_index ${menu_index} + 1
fi

# Other built-in U-Boot boot commands
setenv bootmenu_${menu_index} "Board Information=bdinfo"
setexpr menu_index ${menu_index} + 1
setenv bootmenu_${menu_index} "U-Boot Shell=exit"
setexpr menu_index ${menu_index} + 1
setenv bootmenu_${menu_index} "Reboot=reset"
setexpr menu_index ${menu_index} + 1

# Boot logic for psyopsOS_A
setenv boot_psyopsOS_A "
  echo Booting psyopsOS_A...;
  setenv bootargs \"root=LABEL=${psyopsOS_A_label} ${kernel_params}\" &&
  ext4load ${psyopsOS_A_devtype} ${psyopsOS_A_devnum}:${psyopsOS_A_partnum} ${kernel_addr_r} /kernel &&
  ext4load ${psyopsOS_A_devtype} ${psyopsOS_A_devnum}:${psyopsOS_A_partnum} ${ramdisk_addr_r} /initrd &&
  booti ${kernel_addr_r} ${ramdisk_addr_r} -
"

# Boot logic for psyopsOS_B
setenv boot_psyopsOS_B "
  echo Booting psyopsOS_B...;
  setenv bootargs \"root=LABEL=${psyopsOS_B_label} ${kernel_params}\" &&
  ext4load ${psyopsOS_B_devtype} ${psyopsOS_B_devnum}:${psyopsOS_B_partnum} ${kernel_addr_r} /kernel &&
  ext4load ${psyopsOS_B_devtype} ${psyopsOS_B_devnum}:${psyopsOS_B_partnum} ${ramdisk_addr_r} /initrd &&
  booti ${kernel_addr_r} ${ramdisk_addr_r} -
"

# Timeout and start menu
setenv bootmenu_delay 5
echo "Will boot into ${default_boot_label} in ${bootmenu_delay} seconds..."
bootmenu
run default_bootcmd

"""


_rpi_config_txt = """\
# psyopsOS Raspberry Pi config.txt

arm_64bit=1
arm_boost=1

# Use as little memory as possible for the GPU (requires raspberrypi-bootloader-cutdown package)
gpu_mem=16

# Disable bluetooth, which uses the serial UART (?)
dtoverlay=disable-bt
# Enable the UART in the GPIO pins
enable_uart=1
# Enable debug logging to the UART during boot, show early boot messages over serial
uart_2ndstage=1

# Boot into U-Boot
kernel=u-boot.bin
"""


def rpi_boot_cmd(
    filesystems: Filesystems,
    default_boot_label: str,
    updated: Optional[datetime.datetime] = None,
    kernel_params_append: str = "",
    # The following are not meant to be changed normally
    kernel_params_base: str = "earlyprintk=dbgp console=tty0 console=serial0,115200 loglevel=7",
    kernel_addr_r: str = "0x80200000",
    ramdisk_addr_r: str = "0x82200000",
) -> str:
    """Return a U-Boot boot.cmd file for psyopsOS.

    Parameters:

    default_boot_label:     The label of the default boot entry, should be the label of the A or B filesystem.
    extra_programs:         A dictionary of additional EFI program paths to menu titles.
    updated:                The time the grub.cfg file was last updated.
                            If None, defaults to the current time.
    kernel_params_append:   Parameters to add to the base parameters.

    It is recommended not to change the following arguments, as they are used by the build/update system:
    kernel_params_base:     The kernel parameters to add to both A and B menu entries.
                            You probably don't want to change this, but use kernel_params_append instead.
                            - earlyprintk=dbgp enables early printk, which prints kernel messages to the screen during
                              boot
                            - console=tty0 and console=ttyS0,115200 enable the kernel to print messages to the screen
                              during boot; tty0 is the screen, ttyS0 is the serial port
    kernel_addr_r:          The address of the kernel in RAM.
                            The default value of 0x80200000 is common,
                            as it gives enough room before it for U-Boot stuff.
    ramdisk_addr_r:         The address of the initramfs in RAM.
                            The default value of 0x82200000 is 32MB after the kernel start address,
                            which is large enough for a particularly big kernel.
                            As of 2025, the x86_64 kernels I'm building are 10MB.
    """
    if updated is None:
        updated = datetime.datetime.now()
    sections = [
        _boot_cmd_header_template.format(
            A_label=filesystems.a.label,
            B_label=filesystems.b.label,
            default_label=default_boot_label,
            kernel_addr_r=kernel_addr_r,
            default_boot_label=ramdisk_addr_r,
            kernel_params=f"{kernel_params_base} {kernel_params_append}".strip(),
        ),
        _boot_cmd_body,
    ]
    return "\n\n".join(sections)


def rpi_boot_scr(boot_cmd: str, boot_scr: str):
    """Generate a U-Boot script (binary) from a command file (text)"""
    result = subprocess.run(
        ["mkimage", "-A", "arm", "-T", "script", "-C", "none", "-n", "psyopsOS Boot Script", "-d", boot_cmd, boot_scr],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    if result.returncode != 0:
        logger.error(f"mkimage failed with return code {result.returncode}")
        logger.error(f"stdout: {result.stdout}")
        logger.error(f"stderr: {result.stderr}")
        raise subprocess.CalledProcessError(
            returncode=result.returncode,
            cmd=result.args,
            output=result.stdout,
            stderr=result.stderr
        )
    logger.info(f"stdout: {result.stdout}")
    logger.info(f"stderr: {result.stderr}")


def write_rpi_cfgs_carefully(
    filesystems: Filesystems,
    mountpoint: str,
    default_boot_label: str,
    updated: Optional[datetime.datetime] = None,
    # The following are not meant to be changed normally
    max_old_files: int = 10,
    max_old_days: int = 30,
):
    """Write the Raspbery Pi config files carefully

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
    if not updated:
        updated = datetime.datetime.now()

    boot_cmd = os.path.join(mountpoint, "boot.cmd")
    boot_scr = os.path.join(mountpoint, "boot.scr")
    config_txt = os.path.join(mountpoint, "config.txt")

    write_file_carefully(config_txt, _rpi_config_txt, updated)
    write_file_carefully(boot_cmd, rpi_boot_cmd(filesystems, default_boot_label, updated), updated)

    # Kind of a stupid way to do this, putting it a temp file and then reading it,
    # but it makes write_file_carefully simpler to understand.
    with tempfile.TemporaryDirectory() as tmpdir:
        boot_scr_tmp = os.path.join(tmpdir, "boot.scr")
        rpi_boot_scr(boot_cmd, boot_scr_tmp)
        with open(boot_scr_tmp, "rb") as f:
            boot_scr_contents = f.read()
        write_file_carefully(boot_scr, boot_scr_contents, updated, binary=True)
