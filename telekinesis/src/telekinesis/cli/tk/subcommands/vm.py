"""The vm subcommand"""

from pathlib import Path
import subprocess
import sys
import termios

from telekinesis.config import tkconfig
from telekinesis.rget import rget


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
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
        print("Ctrl+C and Ctrl+Z restored to normal behavior")


def get_ovmf():
    """Download the OVMF firmware image for qemu

    This is somewhat annoying as the project only provides outdated RPM files.

    TODO: we probably need to build this ourselves, unless Alpine packages it in some normal way in the future.
    """
    rget(tkconfig.artifacts.ovmf_url, tkconfig.artifacts.ovmf_rpm)
    if not tkconfig.artifacts.ovmf_extracted_code.exists() or not tkconfig.artifacts.ovmf_extracted_vars.exists():
        in_container_rpm_path = f"/work/{tkconfig.artifacts.ovmf_rpm.name}"
        extract_rpm_script = " && ".join(
            [
                "apk add rpm2cpio",
                "mkdir -p /work/ovmf-extracted",
                "cd /work/ovmf-extracted",
                f"rpm2cpio {in_container_rpm_path} | cpio -idmv",
            ]
        )
        docker_run_cmd = [
            "docker",
            "run",
            "--rm",
            "--volume",
            f"{tkconfig.repopaths.artifacts}:/work",
            "alpine:3.18",
            "sh",
            "-c",
            extract_rpm_script,
        ]
        subprocess.run(docker_run_cmd, check=True)


def vm_grubusb_img(image: Path, macaddr: str):
    """Run the grubusb image in qemu"""
    qemu_cmd = [
        "qemu-system-x86_64",
        "-nic",
        f"user,mac={macaddr}",
        "-serial",
        "stdio",
        # "-display",
        # "none",
        "-m",
        "2048",
        "-drive",
        f"if=pflash,format=raw,readonly=on,file={tkconfig.artifacts.ovmf_extracted_code.as_posix()}",
        "-drive",
        f"if=pflash,format=raw,file={tkconfig.artifacts.ovmf_extracted_vars.as_posix()}",
        "-drive",
        f"format=raw,file={image.as_posix()}",
    ]
    with MungedInterrupts():
        subprocess.run(qemu_cmd, check=True, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)


def vm_grubusb_os():
    """Run the grubusb OS directory in qemu"""
    squashfs = tkconfig.artifacts.grubusb_os_dir / "squashfs"
    qemu_cmd = [
        "qemu-system-x86_64",
        "-nic",
        "user",
        "-serial",
        "stdio",
        # "-display",
        # "none",
        "-m",
        "2048",
        "-kernel",
        f"{tkconfig.artifacts.grubusb_os_dir / 'kernel'}",
        "-initrd",
        f"{tkconfig.artifacts.grubusb_os_dir / 'initramfs'}",
        "-append",
        "root=/dev/sda rootfstype=squashfs rootflags=ro",
        "-drive",
        f"file={squashfs.as_posix()},format=raw,index=0,media=disk",
    ]

    with MungedInterrupts():
        subprocess.run(qemu_cmd, check=True, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
