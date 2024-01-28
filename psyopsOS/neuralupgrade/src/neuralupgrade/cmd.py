"""The psyopsOSimg command

This command is deployed to nodes so that they can update their own OS.
"""


import argparse
import datetime
import logging
import os
import pdb
import subprocess
import sys
import traceback
from typing import Callable, List, Optional

from neuralupgrade import logger
from neuralupgrade.constants import filesystems
from neuralupgrade.grub_cfg import grub_cfg
from neuralupgrade.mount import mountfs


def minisign_verify(pubkey: str, file: str) -> None:
    """Verify a file with minisign."""
    result = subprocess.run(
        ["minisign", "-V", "-p", pubkey, "-m", file],
        text=True,
    )
    if result.returncode != 0:
        raise Exception(f"minisign returned non-zero exit code {result.returncode}")


def activeside() -> str:
    """Return the booted side of a grubusb device (A or B)"""
    with open("/proc/cmdline") as f:
        cmdline = f.read()
    for arg in cmdline.split():
        if arg.startswith("psyopsos="):
            thisside = arg.split("=")[1]
            logger.debug(f"Booted side is {thisside}")
            return thisside
    raise ValueError("Could not determine booted side of grubusb device")


def flipside(side: str) -> str:
    """Given one side of a grubusb image (A or B), return the other side."""
    A = filesystems["a"]["label"]
    B = filesystems["b"]["label"]
    if side not in [A, B]:
        raise ValueError(f"Unknown side {side}")
    opposite = A if side == B else B
    logger.debug(f"Side {opposite} is opposite {side}")
    return opposite


def sides() -> tuple[str, str]:
    """Return the booted side and the nonbooted side of a grubusb device (A or B)"""
    booted = activeside()
    return booted, flipside(booted)


def apply_ostar(tarball: str, osmount: str, verify: bool = True):
    """Apply an ostar to a device"""

    if verify:
        minisign_verify(tarball)

    logger.debug(f"Extracting {tarball} to {osmount}")
    subprocess.run(["tar", "-x", "-f", tarball, "-C", osmount], check=True)
    logger.debug(f"Finished extracting {tarball} to {osmount}")


# Note to self: we release efisys tarballs containing stuff like memtest, which can be extracted on top of an efisys that has grub-install already run on it
def configure_efisys(efisys: str, tarball: Optional[str], default_boot_label: str = filesystems["a"]["label"]):
    """Populate the EFI system partition with the necessary files"""

    memtest = detect_memtest(efisys)

    # I don't understand why I need --boot-directory too, but I do
    cmd = [
        "grub-install",
        "--target=x86_64-efi",
        f"--efi-directory={efisys}",
        f"--boot-directory={efisys}",
        "--removable",
    ]
    subprocess.run(cmd, check=True)

    if tarball:
        logger.debug(f"Extracting efisys tarball {tarball} to {efisys}")
        subprocess.run(["tar", "-x", "-f", tarball, "-C", efisys], check=True)
        logger.debug(f"Finished extracting {tarball} to {efisys}")

    with open(os.path.join(efisys, "grub", "grub.cfg"), "w") as f:
        f.write(grub_cfg(default_boot_label, enable_memtest=memtest))


def detect_memtest(efisys: str) -> bool:
    """Detect whether memtest is installed, given a mounted efisys filesystem"""
    return os.path.exists(os.path.join(efisys, "memtest.efi"))


def apply_ostar_nonbooted(tarball: str, verify: bool = True, skip_grubusb: bool = False):
    """Apply an ostar update to the non-booted side of a grubusb device (A or B)"""
    updated = datetime.datetime.now()
    booted, nonbooted = sides()
    with mountfs(nonbooted) as mountpoint:
        apply_ostar(tarball, mountpoint, verify=verify)
    if not skip_grubusb:
        with mountfs(filesystems["efisys"]["label"]) as mountpoint:
            contents = grub_cfg(
                default_boot_label=nonbooted, enable_memtest=detect_memtest(mountpoint), updated=updated
            )
            with open(os.path.join(mountpoint, "grub", "grub.cfg"), "w") as f:
                f.write(contents)


def idb_excepthook(type, value, tb):
    """Call an interactive debugger in post-mortem mode

    If you do "sys.excepthook = idb_excepthook", then an interactive debugger
    will be spawned at an unhandled exception
    """
    if hasattr(sys, "ps1") or not sys.stderr.isatty():
        sys.__excepthook__(type, value, tb)
    else:
        traceback.print_exception(type, value, tb)
        print
        pdb.pm()


def broken_pipe_handler(func: Callable[[List[str]], int], *arguments: List[str]) -> int:
    """Handler for broken pipes

    Wrap the main() function in this to properly handle broken pipes
    without a giant nastsy backtrace.
    The EPIPE signal is sent if you run e.g. `script.py | head`.
    Wrapping the main function with this one exits cleanly if that happens.

    See <https://docs.python.org/3/library/signal.html#note-on-sigpipe>
    """
    try:
        returncode = func(*arguments)
        sys.stdout.flush()
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        # Convention is 128 + whatever the return code would otherwise be
        returncode = 128 + 1
        sys.exit(returncode)
    return returncode


def getparser() -> tuple[argparse.Namespace, argparse.ArgumentParser]:
    parser = argparse.ArgumentParser("Update psyopsOS boot media")
    parser.add_argument("--debug", "-d", help="Drop into pdb on exception", action="store_true")
    parser.add_argument("--verbose", "-v", help="Verbose logging", action="store_true")
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to run", required=True)

    # verification options
    verify_parser = argparse.ArgumentParser(add_help=False)
    verify_parser.add_argument(
        "--no-verify", dest="verify", action="store_false", help="Skip verification of the ostar tarball"
    )

    # device/mountpoint override options
    overrides_parser = argparse.ArgumentParser(add_help=False)
    overrides_parser.add_argument(
        "--efisys-dev", help="Override device for EFI system partition (found by label by default)"
    )
    overrides_parser.add_argument("--efisys-mountpoint", help="Override mountpoint for EFI system partition")
    overrides_parser.add_argument("--a-dev", help="Override device for A side (found by label by default)")
    overrides_parser.add_argument("--a-mountpoint", help="Override mountpoint for A side")
    overrides_parser.add_argument("--b-dev", help="Override device for B side (found by label by default)")
    overrides_parser.add_argument("--b-mountpoint", help="Override mountpoint for B side")

    # neuralupgrade apply
    apply_parser = subparsers.add_parser(
        "apply", parents=[overrides_parser, verify_parser], help="Apply psyopsOS or EFI system partition updates"
    )
    apply_parser.add_argument(
        "type", nargs="+", choices=["a", "b", "nonbooted", "efisys"], help="The type of update to apply"
    )
    apply_parser.add_argument("--ostar", help="The ostar tarball to apply; required for a/b/nonbooted")
    apply_parser.add_argument(
        "--no-grubusb",
        action="store_true",
        help="Skip updating the grubusb config (only applies when type includes nonbooted)",
    )
    apply_parser.add_argument(
        "--default-boot-label",
        dest="default_boot_label",
        choices=[fs["label"] for fs in filesystems.values()],
        default=filesystems["a"]["label"],
        help="Default boot label for the grubusb image (only applies when type includes nonbooted or efisys)",
    )
    apply_parser.add_argument("--efisys-tarball", help="A tarball to apply when type includes efisys")

    return parser


def main_implementation(*arguments):
    parser = getparser()
    parsed = parser.parse_args(arguments[1:])

    conhandler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    conhandler.setFormatter(formatter)
    logger.addHandler(conhandler)
    if parsed.verbose:
        logger.setLevel(logging.DEBUG)
    if parsed.debug:
        sys.excepthook = idb_excepthook

    logger.debug(f"Arguments: {parsed}")

    if parsed.subcommand == "show":
        parser.error("Not implemented")
    elif parsed.subcommand == "download":
        parser.error("Not implemented")
    elif parsed.subcommand == "check":
        parser.error("Not implemented")
    elif parsed.subcommand == "apply":
        # Check for invalid combinations
        if "nonbooted" in parsed.type and ("a" in parsed.type or "b" in parsed.type):
            parser.error("Cannot specify 'nonbooted' and 'a' or 'b' at the same time")
        ostar_required = "a" in parsed.type or "b" in parsed.type or "nonbooted" in parsed.type
        if ostar_required and not parsed.ostar:
            parser.error("Must specify --ostar when applying ostar updates")

        # Handle actions
        if "nonbooted" in parsed.type:
            parsed.type.remove("nonbooted")
            apply_ostar_nonbooted(parsed.ostar, verify=parsed.verify, skip_grubusb=parsed.no_grubusb)
        for side in ["a", "b"]:
            if side in parsed.type:
                parsed.type.remove(side)
                with mountfs(filesystems[side]["label"]) as mountpoint:
                    apply_ostar(parsed.ostar, mountpoint, verify=parsed.verify)
        if "efisys" in parsed.type:
            parsed.type.remove("efisys")
            configure_efisys(
                filesystems["efisys"]["mountpoint"], parsed.tarball, default_boot_label=parsed.default_boot_label
            )
        if parsed.type:
            parser.error(f"Unknown type argument(s): {parsed.type}")
    elif parsed.subcommand == "install":
        parser.error("Not implemented")
    else:
        parser.error(f"Unknown subcommand {parsed.subcommand}")


def main():
    """Wrapper for main() that handles broken pipes"""
    return broken_pipe_handler(main, *sys.argv)
