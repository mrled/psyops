"""The vm subcommand"""

from pathlib import Path
import subprocess
import sys
import termios
from telekinesis.platforms import Architecture

from telekinesis.config import tkconfig


class MungedInterrupts:
    """Set certain control characters to alternative values.

    A context manager designed for running programs should not be interrupted
    or suspended via Ctrl+C or Ctrl+Z.

    When running a program like QEMU, by default Ctrl+C will kill the program,
    but this is hard to remember because it looks like any regular command
    line. This class changes the terminal settings so that Ctrl+C and Ctrl+Z
    are changed to Ctrl+], which is the default for telnet. This means that
    Ctrl+C and Ctrl+Z will be passed to the running process, so that we can use
    Ctrl+C to send interrupts to the process running *inside* QEMU.

    When setting two control characters to the same value, there is an order of
    precedence: interrupt takes precedence over suspend. This means that Ctrl+]
    will send an interrupt, and it is not possible to suspend the process from
    the terminal.

    See also:
    <https://unix.stackexchange.com/questions/167165/how-to-pass-ctrl-c-to-the-guest-when-running-qemu-with-nographic>
    """

    def __init__(self):
        self.old_settings = None

    def __enter__(self):
        print("WARNING!!")
        print("WARNING!!")
        print("WARNING!! Ctrl+C and Ctrl+Z are changed to Ctrl+]")
        print("WARNING!!")
        print("WARNING!!")
        # Get the current terminal settings, including all control keys and other stuff
        self.old_settings = termios.tcgetattr(sys.stdin)
        # Change the terminal settings so that interrupt and suspend --
        # normally Ctrl+C and Ctrl+Z -- are both changed to Ctrl+].
        # This means that Ctrl+C and Ctrl+Z will be passed to the running process.
        subprocess.run(["stty", "intr", "^]", "susp", "^]"])

    def __exit__(self, exc_type, exc_value, traceback):
        # Restore the terminal settings to what they were before
        if self.old_settings is not None:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
        print("Ctrl+C and Ctrl+Z restored to normal behavior")


def vm_diskimg(architecture: Architecture, image: Path, macaddr: str):
    """Run the disk image in qemu"""
    arch_artifacts = tkconfig.arch_artifacts[architecture.name]
    qemu_cmd = [
        f"qemu-system-{architecture.qemu}",
        "-nic",
        f"user,mac={macaddr}",
        "-serial",
        "stdio",
        # "-display",
        # "none",
        "-m",
        "2048",
        "-drive",
        f"if=pflash,format=raw,readonly=on,file={arch_artifacts.ovmf_extracted_code.as_posix()}",
        "-drive",
        f"if=pflash,format=raw,file={arch_artifacts.ovmf_extracted_vars.as_posix()}",
        "-drive",
        f"format=raw,file={image.as_posix()}",
    ]
    with MungedInterrupts():
        subprocess.run(qemu_cmd, check=True, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)


def vm_osdir(architecture: Architecture):
    """Run the OS directory in qemu"""
    arch_artifacts = tkconfig.arch_artifacts[architecture.name]
    squashfs = arch_artifacts.osdir_path / "squashfs"
    qemu_cmd = [
        f"qemu-system-{architecture.qemu}",
        "-nic",
        "user",
        "-serial",
        "stdio",
        # "-display",
        # "none",
        "-m",
        "2048",
        "-kernel",
        f"{arch_artifacts.osdir_path / 'kernel'}",
        "-initrd",
        f"{arch_artifacts.osdir_path / 'initramfs'}",
        "-append",
        "root=/dev/sda rootfstype=squashfs rootflags=ro",
        "-drive",
        f"file={squashfs.as_posix()},format=raw,index=0,media=disk",
    ]

    with MungedInterrupts():
        subprocess.run(qemu_cmd, check=True, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
