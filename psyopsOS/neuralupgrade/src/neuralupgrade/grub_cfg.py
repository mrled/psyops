"""The grub.cfg file for psyopsOS."""

import datetime
from typing import Optional


_header_format = """\
# psyopsOS grub.cfg

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


menuentry "Welcome to psyopsOS grubusb. GRUB configuration last updated: {last_updated}" {
    echo "Welcome to psyopsOS grubusb. GRUB configuration last updated: {last_updated}"
}
menuentry "----------------------------------------" {
    echo "----------------------------------------"
}
"""

_footer_format = """\
menuentry "UEFI fwsetup" {
    fwsetup
}

menuentry "Reboot" {
    reboot
}

menuentry "Poweroff" {
    halt
}

menuentry "Exit GRUB" {
    exit
}
"""

_psyopsOS_entry_format = """\
menuentry "{label}" {
    search --no-floppy --label {label} --set root
    linux /kernel ro psyopsos={label} {kernel_params}
    initrd /initramfs
}
"""

_memtest_entry_format = """\
menuentry "MemTest86 EFI (64-bit)" {
    insmod part_gpt
    insmod fat
    insmod chain
    search --no-floppy --label {label_efisys} --set root
    chainloader /memtest64.efi
}
"""


def grub_cfg(
    default_boot_label: str,
    enable_memtest: bool = True,
    updated: Optional[datetime.datetime] = None,
    kernel_params_append: str = "",
    # The following are not meant to be changed normally
    kernel_params_base: str = "earlyprintk=dbgp console=tty0 console=ttyS0,115200",
    label_psyopsOS_A: str = "psyopsOS-A",
    label_psyopsOS_B: str = "psyopsOS-B",
    label_efisys: str = "PSYOPSOSEFI",
) -> str:
    """Return a grub.cfg file for psyopsOS.

    Arguments
    default_boot_label:     The label of the default boot entry, either psyopsOS-A or psyopsOS-B.
    enable_memtest:         If True, add a menu entry for MemTest86 EFI.
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
    label_psyopsOS_A:       The label of the A side of the psyopsOS grubusb image.
                            Changing this will break assumptions in the build/update system.
    label_psyopsOS_B:       The label of the B side of the psyopsOS grubusb image.
                            Changing this will break assumptions in the build/update system.
    label_efisys:           The label of the EFI system partition.
                            Changing this will break assumptions in the build/update system.
    """
    kernel_params = f"{kernel_params_base} {kernel_params_append}".strip()
    if not updated:
        updated = datetime.datetime.now()
    sections = [
        _header_format.format(default_boot_label=default_boot_label, last_updated=updated.strftime("%Y%m%d-%H%M%S")),
        _psyopsOS_entry_format.format(label=label_psyopsOS_A, kernel_params=kernel_params),
        _psyopsOS_entry_format.format(label=label_psyopsOS_B, kernel_params=kernel_params),
    ]
    if enable_memtest:
        sections.append(_memtest_entry_format.format(label_efisys=label_efisys))
    sections.append(_footer_format)

    return "\n\n".join(sections)
