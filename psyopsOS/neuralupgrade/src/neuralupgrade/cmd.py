"""The psyopsOSimg command

This command is deployed to nodes so that they can update their own OS.
"""


import argparse
import datetime
import logging
import os
import pdb
import pprint
import shutil
import subprocess
import sys
import threading
import traceback
from typing import Any, Callable, List, Optional

from neuralupgrade import logger
from neuralupgrade.constants import filesystems

from neuralupgrade.grub_cfg import grub_cfg
from neuralupgrade.mount import mountfs


def minisign_verify(file: str, pubkey: Optional[str] = None) -> None:
    """Verify a file with minisign."""
    pubkey_args = ["-p", pubkey] if pubkey else []
    cmd = ["minisign", "-V", *pubkey_args, "-m", file]
    logger.debug(f"Running minisign: {cmd}")
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        raise Exception(f"minisign returned non-zero exit code {result.returncode}")


def parse_psyopsOS_minisig_trusted_comment(comment: Optional[str] = None, file: Optional[str] = None) -> dict:
    """Parse a trusted comment from a psyopsOS minisig

    Example file contents:

        untrusted comment: signature from minisign secret key
        RURFlbvwaqbpRv1RGZk6b0TkCUmJZvNRKVqfyveYOicg3g1FR6EUmvwkPGwB8yFJ+m9l/Al6sixSOAUVQDwwsfs23Coa9xEHBwI=
        trusted comment: psyopsOS filename=psyopsOS.grubusb.os.20240129-155151.tar version=20240129-155151 kernel=6.1.75-0-lts alpine=3.18
        nISvkyfCnUI6Xjgr0vz+g4VbymHJh8rvPAHKncAm5sXVT9HMyQV5+HhgvMP3NLaRKSCng6VAYkIufXYkCmobCQ==

    Can accept either just the "trusted comment: " line, or a path to the minisig file.

    Returns a dict of key=value pairs, like:

        {
            "filename": "psyopsOS.grubusb.os.20240129-155151.tar",
            "version": "20240129-155151",
            "kernel": "6.1.75-0-lts",
            "alpine": "3.18",
        }
    """
    if comment and file:
        raise ValueError("Cannot specify both comment and file")
    if not comment and not file:
        raise ValueError("Must specify either comment or file")

    prefix = "trusted comment: psyopsOS "
    if file:
        with open(file) as f:
            for line in f.readlines():
                if line.startswith(prefix):
                    return parse_psyopsOS_minisig_trusted_comment(comment=line)
        raise ValueError(f"Could not find trusted comment in {file}")

    if not comment.startswith(prefix):
        raise ValueError(f"Invalid trusted comment: {comment}")

    # parse all the key=value pairs in the trusted comment
    metadata = {kv[0]: kv[1] for kv in [x.split("=") for x in comment[len(prefix) :].split()]}
    return metadata


def parse_psyopsOS_grub_info_comment(comment: Optional[str] = None, file: Optional[str] = None) -> dict:
    """Parse a trusted comment from a psyopsOS minisig

    The comment comes from grub.cfg, like this:

        #### The next line is used by neuralupgrade to show information about the current configuration.
        # neuralupgrade-info: last_updated={last_updated} default_boot_label={default_boot_label} memtest_enabled={memtest_enabled}
        ####

    Can accept either just the "# neuralupgrade-info: " line, or a path to the grub.cfg file.
    """
    if comment and file:
        raise ValueError("Cannot specify both comment and file")
    if not comment and not file:
        raise ValueError("Must specify either comment or file")

    prefix = "# neuralupgrade-info: "
    if file:
        with open(file) as f:
            for line in f.readlines():
                if line.startswith(prefix):
                    return parse_psyopsOS_grub_info_comment(comment=line)
        raise ValueError(f"Could not find trusted comment in {file}")

    if not comment.startswith(prefix):
        raise ValueError(f"Invalid trusted comment: {comment}")

    # parse all the key=value pairs in the trusted comment
    metadata = {kv[0]: kv[1] for kv in [x.split("=") for x in comment[len(prefix) :].split()]}
    return metadata


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


def getinfo_os_mount(mountpoint: str) -> dict:
    """Return information about an os mountpoint"""
    # with open(os.path.join(mountpoint, "kernel.version")) as f:
    #     kvers = f.read().strip()
    # with open(os.path.join(mountpoint, "squahfs.alpine_version")) as f:
    #     alpine_version = f.read().strip()
    minisigdata = parse_psyopsOS_minisig_trusted_comment(
        file=os.path.join(mountpoint, "psyopsOS.grubusb.os.tar.minisig")
    )
    return minisigdata


def mount_and_do_offthread(label: str, operation: Callable[[], Any]) -> threading.Thread:
    """Mount a filesystem by label and return the contents of a file, in another thread; return the thread object"""

    def _mount_and_do():
        with mountfs(label) as mountpoint:
            return operation()

    thread = threading.Thread(target=_mount_and_do)
    thread.start()
    return thread


def show_booted_old():
    """Show information about the booted side of a grubusb device"""
    booted, nonbooted = sides()

    with mountfs(booted) as mountpoint:
        try:
            booted_info = parse_psyopsOS_minisig_trusted_comment(
                file=os.path.join(mountpoint, "psyopsOS.grubusb.os.tar.minisig")
            )
        except FileNotFoundError:
            booted_info = {"error": "missing minisig"}
    with mountfs(nonbooted) as mountpoint:
        try:
            nonbooted_info = parse_psyopsOS_minisig_trusted_comment(
                file=os.path.join(mountpoint, "psyopsOS.grubusb.os.tar.minisig")
            )
        except FileNotFoundError:
            booted_info = {"error": "missing minisig"}
    with mountfs(filesystems["efisys"]["label"]) as mountpoint:
        efisys_info = parse_psyopsOS_grub_info_comment(file=os.path.join(mountpoint, "grub", "grub.cfg"))

    result = {
        booted: {
            "mountpoint": filesystems[booted]["mountpoint"],
            "running": True,
            "next_boot": False,
            **booted_info,
        },
        nonbooted: {
            "mountpoint": filesystems[nonbooted]["mountpoint"],
            "running": False,
            "next_boot": False,
            **nonbooted_info,
        },
        filesystems["efisys"]["label"]: {
            "mountpoint": filesystems["efisys"]["mountpoint"],
            **efisys_info,
        },
    }
    result[efisys_info["default_boot_label"]]["next_boot"] = True
    return result


def show_booted():
    """Show information about the grubusb device

    Uses threads to speed up the process of mounting the filesystems and reading the minisig files.
    """
    booted, nonbooted = sides()
    efisys = filesystems["efisys"]["label"]

    result = {
        booted: {
            "mountpoint": filesystems[booted]["mountpoint"],
            "running": True,
            "next_boot": False,
        },
        nonbooted: {
            "mountpoint": filesystems[nonbooted]["mountpoint"],
            "running": False,
            "next_boot": False,
        },
        efisys: {
            "mountpoint": filesystems["efisys"]["mountpoint"],
        },
    }

    def _get_os_tc(label: str):
        with mountfs(label) as mountpoint:
            try:
                info = parse_psyopsOS_minisig_trusted_comment(
                    file=os.path.join(mountpoint, "psyopsOS.grubusb.os.tar.minisig")
                )
            except FileNotFoundError:
                info = {"error": "missing minisig"}
            except Exception as exc:
                efisys_info = {"error": str(exc)}
        result[label] = {**result[label], **info}

    def _get_grub_info():
        with mountfs(filesystems["efisys"]["label"]) as mountpoint:
            try:
                efisys_info = parse_psyopsOS_grub_info_comment(file=os.path.join(mountpoint, "grub", "grub.cfg"))
            except FileNotFoundError:
                efisys_info = {"error": "missing grub.cfg"}
            except Exception as exc:
                efisys_info = {"error": str(exc)}
        result[efisys] = {**result[efisys], **efisys_info}

    nonbooted_thread = threading.Thread(target=_get_os_tc, args=(booted,))
    nonbooted_thread.start()
    booted_thread = threading.Thread(target=_get_os_tc, args=(nonbooted,))
    booted_thread.start()
    efisys_thread = threading.Thread(target=_get_grub_info)
    efisys_thread.start()

    booted_thread.join()
    nonbooted_thread.join()
    efisys_thread.join()

    # Handle these after the threads have joined
    # I'm not sure what happens if the os tc threads and the efi thread tries to write to the same dict at the same time
    next_boot = result[efisys]["default_boot_label"]
    result[next_boot]["next_boot"] = True

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
        shutil.copy(minisig, os.path.join(osmount, "psyopsOS.grubusb.os.tar.minisig"))
        logger.debug(f"Copied {minisig} to {osmount}/psyopsOS.grubusb.os.tar.minisig")
    except FileNotFoundError:
        logger.warning(f"Could not find {minisig}, partition will not know its version")
    logger.debug(f"Finished applying {tarball} to {osmount}")


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
    logger.debug(f"Running grub-install: {cmd}")
    subprocess.run(cmd, check=True)

    if tarball:
        logger.debug(f"Extracting efisys tarball {tarball} to {efisys}")
        subprocess.run(["tar", "-x", "-f", tarball, "-C", efisys], check=True)
        logger.debug(f"Finished extracting {tarball} to {efisys}")

    logger.debug(f"Writing {efisys}/grub/grub.cfg")
    with open(os.path.join(efisys, "grub", "grub.cfg"), "w") as f:
        f.write(grub_cfg(default_boot_label, enable_memtest=memtest))

    logger.debug("Done configuring efisys")


def detect_memtest(efisys: str) -> bool:
    """Detect whether memtest is installed, given a mounted efisys filesystem"""
    exists = os.path.exists(os.path.join(efisys, "memtest64.efi"))
    logger.debug(f"memtest.efi exists in {efisys}: {exists}")
    return exists


def apply_ostar_nonbooted(
    tarball: str, verify: bool = True, verify_pubkey: Optional[str] = None, skip_grubusb: bool = False
):
    """Apply an ostar update to the non-booted side of a grubusb device (A or B)"""
    updated = datetime.datetime.now()
    booted, nonbooted = sides()
    with mountfs(nonbooted) as mountpoint:
        apply_ostar(tarball, mountpoint, verify=verify, verify_pubkey=verify_pubkey)
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
    verify_parser.add_argument(
        "--pubkey",
        default="/etc/psyopsOS/minisign.pubkey",
        help="Public key to use for verification (default: %(default)s)",
    )

    # device/mountpoint override options
    overrides_parser = argparse.ArgumentParser(add_help=False)
    overrides_parser.add_argument(
        "--efisys-dev", help="Override device for EFI system partition (found by label by default)"
    )
    overrides_parser.add_argument(
        "--efisys-mountpoint", help="Override mountpoint for EFI system partition (found by label in fstab by default)"
    )
    overrides_parser.add_argument("--a-dev", help="Override device for A side (found by label by default)")
    overrides_parser.add_argument(
        "--a-mountpoint", help="Override mountpoint for A side (found by label in fstab by default)"
    )
    overrides_parser.add_argument("--b-dev", help="Override device for B side (found by label by default)")
    overrides_parser.add_argument(
        "--b-mountpoint", help="Override mountpoint for B side (found by label in fstab by default)"
    )

    # neuralupgrade show
    show_parser = subparsers.add_parser("show", parents=[overrides_parser], help="Show information about boot media")
    show_parser.add_argument("--minisig", help="Show information from the minisig file of a specific ostar tarball")

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
        if parsed.minisig:
            metadata = parse_psyopsOS_minisig_trusted_comment(file=parsed.minisig)
        else:
            metadata = show_booted()
        pprint.pprint(metadata, sort_dicts=False)
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
            apply_ostar_nonbooted(
                parsed.ostar, verify=parsed.verify, verify_pubkey=parsed.pubkey, skip_grubusb=parsed.no_grubusb
            )
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
        pprint.pprint(show_booted(), sort_dicts=False)
    elif parsed.subcommand == "install":
        parser.error("Not implemented")
    else:
        parser.error(f"Unknown subcommand {parsed.subcommand}")


def main():
    return broken_pipe_handler(main_implementation, *sys.argv)
