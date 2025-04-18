import datetime
import os
import subprocess
import tempfile
from typing import Optional

from neuralupgrade import logger
from neuralupgrade.filesystems import Filesystems
from neuralupgrade.filewriter import write_file_carefully
from neuralupgrade.firmware.timestamp import firwmare_update_timestamp


# A string.Template that sets variables in the boot.cmd file.
_boot_cmd_header_fmt = """\
# {last_updated}
# IMPORTANT: LEAVE THE LINE ABOVE THIS COMMENT ALONE.
# This script doesn't know what partition contains it,
# but it can ask U-Boot to find all partitions,
# load boot.cmd if it exists,
# and compare the contents of the first few bytes.

# psyopsOS boot.cmd
# Variables populated by neuralupgrade

#### The next line is used by neuralupgrade to show information about the current configuration.
# neuralupgrade-info: last_updated={last_updated} default_boot_label={default_boot_label}
####

# The date this was last updated
# IMPORTANT: DO NOT CHANGE THE NAME OF THIS VARIABLE.
# The length of the variable **name** must be accounted for in the memory comparison below.
setenv last_updated {last_updated}

# The partition labels for the A and B filesystems.
setenv psyopsOS_A_label {A_label}
setenv psyopsOS_B_label {B_label}

# The default boot label (must be one of A or B)
setenv default_boot_label {default_boot_label}

# Starting addresses for kernel and initramfs.
# These are JUST used during boot and do not affect OS runtime;
# Linux will move itself around in memory as needed,
# and initrd is mounted to a tmpfs instance at boot,
# so the original memory buffer from U-Boot is freed.
setenv kernel_addr_r {kernel_addr_r}
setenv ramdisk_addr_r {ramdisk_addr_r}
setenv dtb_addr_r {dtb_addr_r}
setenv dtbo_1_addr_r {dtbo_1_addr_r}

# Kernel commandline parameters to each A/B side
setenv kernel_params "{kernel_params}"

"""

_boot_cmd_body_simple = """\
echo "Welcome to psyopsOS! Simple boot command loaded. Dropping to U-Boot shell..."
echo "----------------------------------------------------------------------------"
echo ""
exit
"""

# A string, with no variables, that uses the variables set in the header.
_boot_cmd_body = """\
echo "Welcome to psyopsOS. U-Boot configuration last updated: ${last_updated}"
echo ""

# Uncomment to drop into a shell early
# echo "Dropping into U-Boot shell..."
# exit

# Initialize USB
echo "psyopsOS: Initializing USB..."
usb start
echo "psyopsOS: USB initialized"

# Clear previous bootmenu
# TODO: is this really necessary?
for i in 0 1 2 3 4 5; do
    setenv bootmenu_${i}
done

# Probe for psyopsOS A and B partitions by their partition label.
# Currently only look on mmc and usb devices because my only U-Boot platform is the Raspberry Pi.
setenv probe_devtypes "mmc usb"
# setenv probe_devtypes "mmc usb sata scsi"

echo "psyopsOS: Probing for boot.cmd on ${probe_devtypes} devices..."
setenv bootdev_type ""
setenv bootdev_num ""
for devtype in ${probe_devtypes}; do
    for devnum in 0 1 2; do
        echo "Probing ${devtype} ${devnum} for boot.cmd..."
        if ${devtype} dev ${devnum}; then
            # Assume that the boot partition will only ever be the first one on a device
            if load ${devtype} ${devnum}:1 ${kernel_addr_r} /boot.cmd; then
                echo "Found boot.cmd on ${devtype} ${devnum}:1"
                # We know we found **SOME** boot.cmd, but we don't know if it's the one that's currently running.

                # Because the load worked, ${kernel_addr_r} has a value of something like '# 20250415-003744...'
                # Skip two characters to skip the '# ':
                setexpr header_timestamp_r ${kernel_addr_r} + 0x2

                # Now build a string in RAM that contains **this** boot.cmd's last_updated timestamp.
                env export -t ${ramdisk_addr_r} last_updated
                # Now ${ramdisk_addr_r} has a value of something like 'last_updated=20250415-003744'
                # Skip 13 characters to skip the 'last_updated=':
                setexpr this_timestamp_r ${ramdisk_addr_r} + 0xd

                # Compare the two timestamps, which are 15 bytes each
                if cmp.b ${header_timestamp_r} ${this_timestamp_r} 0xf; then
                    echo "Found our own boot.cmd file on ${devtype} ${devnum}:0"
                    setenv bootdev_type ${devtype}
                    setenv bootdev_num ${devnum}
                else
                    echo "Found a DIFFERENT boot.cmd file on ${devtype} ${devnum}:0, not using it"
                fi
            else
                echo "No boot.cmd found on ${devtype} ${devnum}:0"
            fi
        else
            echo "No ${devtype} ${devnum} device found"
        fi
    done
done

if test "${bootdev_type}" = ""; then
    echo "ERROR: No bootable device found!"
    # Drop into the U-Boot shell
    exit
fi
echo "psyopsOS: Found bootable device: ${bootdev_type} ${bootdev_num}"

echo "psyopsOS: Probing for psyopsOS A and B partitions..."
setenv psyopsOS_A_partnum ""
setenv psyopsOS_B_partnum ""
for partnum in 2 3 4 5 6 7 8; do
    if load ${bootdev_type} ${bootdev_num}:${partnum} ${kernel_addr_r} ${psyopsOS_A_label}; then
        echo "Found ${A_label} on ${bootdev_type} ${bootdev_num}:${partnum}"
        setenv psyopsOS_A_partnum ${partnum}
    else
        if load ${bootdev_type} ${bootdev_num}:${partnum} ${kernel_addr_r} ${psyopsOS_B_label}; then
            echo "Found ${B_label} on ${bootdev_type} ${bootdev_num}:${partnum}"
            setenv psyopsOS_B_partnum ${partnum}
        fi
    fi
done

# Exit with an error if it can't find anything to boot
if test "${psyopsOS_A_partnum}" = "" && test "${psyopsOS_B_partnum}" = ""; then
    echo "ERROR: No psyopsOS partitions found!"
    # Drop into the U-Boot shell
    exit
fi
echo "psyopsOS: Finished probing for psyopsOS A and B partitions"

# Fallback error message if default_boot_label is not found
setenv default_bootcmd "echo "ERROR: Default boot label ${default_boot_label} not found! Exiting to U-Boot shell..."; exit;"

# Boot commands for each label
setenv menu_index 0
if test "${psyopsOS_A_partnum}" != ""; then
    setenv bootmenu_${menu_index} "${psyopsOS_A_label}=run boot_psyopsOS_A"
    if test "${default_boot_label}" = "${psyopsOS_A_label}"; then
        setenv default_bootcmd "run boot_psyopsOS_A"
    fi
    setexpr menu_index ${menu_index} + 1
fi
if test "${psyopsOS_B_partnum}" != ""; then
    setenv bootmenu_${menu_index} "${psyopsOS_B_label}=run boot_psyopsOS_B"
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

dtb_file_path="/dtbs/bcm2711-rpi-4-b.dtb"
dtbo_file_path="/dtbs/overlays/disable-bt.dtbo"

# Boot logic for psyopsOS_A
setenv boot_psyopsOS_A "
  echo Booting psyopsOS-A...;
  setenv bootargs \"psyopsos=psyopsOS-A ${kernel_params}\" &&
  ext4load ${bootdev_type} ${bootdev_num}:${psyopsOS_A_partnum} ${kernel_addr_r} /kernel &&
  ext4load ${bootdev_type} ${bootdev_num}:${psyopsOS_A_partnum} ${ramdisk_addr_r} /initramfs &&
  setenv initrdsize \${filesize} &&
  ext4load ${bootdev_type} ${bootdev_num}:${psyopsOS_A_partnum} ${dtb_addr_r} ${dtb_file_path} &&
  fdt addr ${dtb_addr_r} &&
  fdt resize &&
  ext4load ${bootdev_type} ${bootdev_num}:${psyopsOS_A_partnum} ${dtbo_1_addr_r} ${dtbo_file_path} &&
  fdt apply ${dtbo_1_addr_r} &&
  fdt print /soc/serial@7e201000 &&
  fdt print /aliases &&
  echo "Booting kernel..." &&
  booti ${kernel_addr_r} ${ramdisk_addr_r}:\${initrdsize} ${dtb_addr_r}
"

# Boot logic for psyopsOS_B
setenv boot_psyopsOS_B "
  echo Booting psyopsOS-B...;
  setenv bootargs \"psyopsos=psyopsOS-B ${kernel_params}\" &&
  ext4load ${bootdev_type} ${bootdev_num}:${psyopsOS_B_partnum} ${kernel_addr_r} /kernel &&
  ext4load ${bootdev_type} ${bootdev_num}:${psyopsOS_B_partnum} ${ramdisk_addr_r} /initramfs &&
  setenv initrdsize \${filesize} &&
  ext4load ${bootdev_type} ${bootdev_num}:${psyopsOS_B_partnum} ${dtb_addr_r} ${dtb_file_path} &&
  fdt addr ${dtb_addr_r} &&
  fdt resize &&
  ext4load ${bootdev_type} ${bootdev_num}:${psyopsOS_B_partnum} ${dtbo_1_addr_r} ${dtbo_file_path} &&
  fdt apply ${dtbo_1_addr_r} &&
  fdt print /soc/serial@7e201000 &&
  fdt print /aliases &&
  echo "Booting kernel..." &&
  booti ${kernel_addr_r} ${ramdisk_addr_r}:\${initrdsize} ${dtb_addr_r}
"

# Timeout and start menu
setenv bootmenu_delay 5
echo "Will boot into ${default_boot_label} in ${bootmenu_delay} seconds..."
# TODO: MUST REBUILD U-BOOT TO ENABLE CONFIG_CMD_BOOTMENU
# bootmenu
# run default_bootcmd

echo "Dummy print bootmenu (not necessary once we rebuild U-Boot with CONFIG_CMD_BOOTMENU enabled):"
for i in 0 1 2 3 4; do
    printenv bootmenu_${i}
done

echo "${boot_psyopsOS_A}"
run boot_psyopsOS_A

"""


_rpi_config_txt = """\
# psyopsOS Raspberry Pi config.txt

arm_64bit=1
arm_boost=1

# Use as little memory as possible for the GPU (requires raspberrypi-bootloader-cutdown package)
# In theory this could be as low as 16 but 64 is more conservative
gpu_mem=64

# Disable bluetooth, which uses the serial UART (?)
# If the Raspberry Pi firmware loads the kernel directly (that is, if kernel= is set to a Linux binary),
# this does TWO Things:
# 1. It applies the device tree overlay file in /boot/overlays/disable-bt.dtbo
# 2. It uses the mailbox interface to set up the PL011 clock and re-configure GPIO 14/15 into the UART function
# If the firmware loads U-Boot (kernel=u-boot.bin), it doesn't load the overlay file,
# and U-Boot will have to apply the disable-bt.dbto file itself.
# However, it is STILL REQUIRED to properly configure the GPIO pins (I think this is "pin-mux" or "pinmux").
dtoverlay=disable-bt

# Enable the UART in the GPIO pins
enable_uart=1
# Enable debug logging to the UART during boot, show early boot messages over serial
# For when start4.elf is running, before U-Boot (or a kernel) is loaded
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
    kernel_params_base: str = "earlyprintk=dbgp console=tty0 console=ttyAMA0,115200 loglevel=7",
    kernel_addr_r: str = "0x80200000",
    ramdisk_addr_r: str = "0x82200000",
    dtb_addr_r: str = "0x8a200000",
    dtbo_1_addr_r: str = "0x8a100000",
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
                            It is almost almost 2GiB after 0x0 start address:
                            0x82200000 / 0x100000 = 2082.0
    ramdisk_addr_r:         The address of the initramfs in RAM.
                            The default value of 0x82200000 is 32MB after the kernel start address,
                            which is large enough for a particularly big kernel.
                            As of 2025, the Raspberry Pi kernels I'm using from Alpine are about 10MB.
                            (0x82200000 - 0x80200000) / 0x100000 = 32.0
    dtb_addr_r:             The address of the device tree blob in RAM.
                            As of 2025, the Raspberry Pi ramdisks I'm building are about 55MB.
                            0x8a200000 is 128MB from the ramdisk start address:
                            (0x8a200000 - 0x82200000) / 0x100000 = 128.0
    dtbo_1_addr_r:          The address of the first device tree overlay in RAM.
    """
    if updated is None:
        updated = datetime.datetime.now()
    sections = [
        _boot_cmd_header_fmt.format(
            A_label=filesystems.a.label,
            B_label=filesystems.b.label,
            last_updated=firwmare_update_timestamp(updated),
            default_boot_label=default_boot_label,
            kernel_addr_r=kernel_addr_r,
            ramdisk_addr_r=ramdisk_addr_r,
            dtb_addr_r=dtb_addr_r,
            dtbo_1_addr_r=dtbo_1_addr_r,
            kernel_params=f"{kernel_params_base} {kernel_params_append}".strip(),
        ),
        _boot_cmd_body,
        # _boot_cmd_body_simple,
    ]
    return "\n\n".join(sections)


def rpi_boot_scr(boot_cmd: str, boot_scr: str):
    """Generate a U-Boot script (binary) from a command file (text)"""
    result = subprocess.run(
        ["mkimage", "-A", "arm", "-T", "script", "-C", "none", "-n", "psyopsOS Boot Script", "-d", boot_cmd, boot_scr],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        logger.error(f"mkimage failed with return code {result.returncode}")
        logger.error(f"stdout: {result.stdout}")
        logger.error(f"stderr: {result.stderr}")
        raise subprocess.CalledProcessError(
            returncode=result.returncode, cmd=result.args, output=result.stdout, stderr=result.stderr
        )
    logger.info(f"stdout: {result.stdout}")
    logger.info(f"stderr: {result.stderr}")


def write_rpi_cfgs_carefully(
    filesystems: Filesystems,
    mountpoint: str,
    default_boot_label: str,
    updated: Optional[datetime.datetime] = None,
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
