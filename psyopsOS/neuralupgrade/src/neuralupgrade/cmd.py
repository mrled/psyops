"""The psyopsOSimg command

This command is deployed to nodes so that they can update their own OS.
"""

import argparse
import logging
import os
import pdb
import pprint
import sys
import traceback
from typing import Callable, List

from neuralupgrade import logger

from neuralupgrade.downloader import download_update
from neuralupgrade.filesystems import Filesystem, Filesystems
from neuralupgrade.grub_cfg import write_grub_cfg_carefully
from neuralupgrade.osupdates import apply_updates, parse_psyopsOS_minisig_trusted_comment, show_booted


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


def get_argparse_help_string(name: str, parser: argparse.ArgumentParser, wrap: int = 80) -> str:
    """Generate a docstring for an argparse parser that shows the help for the parser and all subparsers, recursively.

    Based on an idea from <https://github.com/pdoc3/pdoc/issues/89>

    Arguments:
    * `name`: The name of the program
    * `parser`: The parser
    * `wrap`: The number of characters to wrap the help text to (0 to disable)
    """

    def help_formatter(prog):
        return argparse.HelpFormatter(prog, width=wrap)

    def get_parser_help_recursive(parser: argparse.ArgumentParser, cmd: str = "", root: bool = True):
        docstring = ""
        if not root:
            docstring += "\n" + "_" * 72 + "\n\n"
        docstring += f"> {cmd} --help\n"
        parser.formatter_class = help_formatter
        docstring += parser.format_help()

        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for subcmd, subparser in action.choices.items():
                    docstring += get_parser_help_recursive(subparser, f"{cmd} {subcmd}", root=False)
        return docstring

    docstring = get_parser_help_recursive(parser, name)
    return docstring


def getparser(prog=None) -> tuple[argparse.Namespace, argparse.ArgumentParser]:
    parser = argparse.ArgumentParser(prog=prog, description="Update psyopsOS boot media")
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
    overrides_parser.add_argument(
        "--efisys-label", default="PSYOPSOSEFI", help="Override label for EFI system partition, default: %(default)s"
    )
    overrides_parser.add_argument("--a-dev", help="Override device for A side (found by label by default)")
    overrides_parser.add_argument(
        "--a-mountpoint", help="Override mountpoint for A side (found by label in fstab by default)"
    )
    overrides_parser.add_argument(
        "--a-label", default="psyopsOS-A", help="Override label for A side, default: %(default)s"
    )
    overrides_parser.add_argument("--b-dev", help="Override device for B side (found by label by default)")
    overrides_parser.add_argument(
        "--b-mountpoint", help="Override mountpoint for B side (found by label in fstab by default)"
    )
    overrides_parser.add_argument(
        "--b-label", default="psyopsOS-B", help="Override label for B side, default: %(default)s"
    )

    # Repository options
    repository_parser = argparse.ArgumentParser(add_help=False)
    repository_parser.add_argument(
        "--repository",
        default="https://psyops.micahrl.com/os",
        help="URL for the psyopsOS update repository, default: %(default)s",
    )
    repository_parser.add_argument(
        "--psyopsOS-filename-format",
        default="psyopsOS.grubusb.os.{version}.tar",
        help="The format string for the versioned grubusb EFI system partition tarfile. Used as the base for the filename in S3, and also of the signature file.",
    )
    repository_parser.add_argument(
        "--psyopsESP-filename-format",
        default="psyopsOS.grubusb.efisys.{version}.tar",
        help="The format string for the versioned grubusb OS tarfile. Used as the base for the filename in S3, and also of the signature file.",
    )

    # neuralupgrade show
    show_parser = subparsers.add_parser("show", parents=[overrides_parser], help="Show information about boot media")
    show_parser.add_argument("--minisig", help="Show information from the minisig file of a specific ostar tarball")

    # neuralupgrade download
    download_parser = subparsers.add_parser(
        "download", parents=[overrides_parser, repository_parser, verify_parser], help="Download updates"
    )
    download_parser.add_argument(
        "--version", default="latest", help="Version of the update to download, default: %(default)s"
    )
    download_parser.add_argument(
        "--type",
        default=["psyopsOS", "psyopsESP"],
        nargs="+",
        choices=["psyopsOS", "psyopsESP"],
        help="The type of update to download",
    )
    download_parser.add_argument(
        "output",
        help="Where to download update(s). If it ends in a slash, treated as a directory and download the default filename of the update. If multiple types are passed, this must be a directory.",
    )

    # neuralupgrade apply
    apply_parser = subparsers.add_parser(
        "apply",
        parents=[overrides_parser, verify_parser],
        help="Apply psyopsOS or EFI system partition updates",
    )
    apply_parser.add_argument(
        "type", nargs="+", choices=["a", "b", "nonbooted", "efisys"], help="The type of update to apply"
    )
    apply_parser.add_argument(
        "--default-boot-label",
        dest="default_boot_label",
        help="Default boot label if writing the grub.cfg file",
    )
    apply_parser.add_argument("--ostar", help="The ostar tarball to apply; required for a/b/nonbooted")
    apply_parser.add_argument(
        "--no-grubusb",
        action="store_true",
        help="Skip updating the grubusb config (only applies when type includes nonbooted)",
    )
    apply_parser.add_argument(
        "--esptar", help="A tarball to apply to the EFI System Partition when type includes efisys"
    )

    # neuralupgrade set-default
    set_default_parser = subparsers.add_parser(
        "set-default", parents=[overrides_parser], help="Set the default boot label in the grubusb config"
    )
    set_default_parser.add_argument("label", help="The label to set as the default boot label")

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

    filesystems = Filesystems(
        efisys=Filesystem(parsed.efisys_label, device=parsed.efisys_dev, mountpoint=parsed.efisys_mountpoint),
        a=Filesystem(parsed.a_label, device=parsed.a_dev, mountpoint=parsed.a_mountpoint),
        b=Filesystem(parsed.b_label, device=parsed.b_dev, mountpoint=parsed.b_mountpoint),
    )

    if parsed.subcommand == "show":
        if parsed.minisig:
            metadata = parse_psyopsOS_minisig_trusted_comment(file=parsed.minisig)
        else:
            metadata = show_booted(filesystems)
        pprint.pprint(metadata, sort_dicts=False)

    elif parsed.subcommand == "download":
        output: str = parsed.output
        if len(parsed.type) > 1 and not output.endswith("/"):
            output += "/"
        if "psyopsOS" in parsed.type:
            download_update(
                parsed.repository,
                parsed.psyopsOS_filename_format,
                parsed.version,
                output,
                pubkey=parsed.pubkey,
                verify=parsed.verify,
            )
        if "psyopsESP" in parsed.type:
            download_update(
                parsed.repository,
                parsed.psyopsESP_filename_format,
                parsed.version,
                output,
                pubkey=parsed.pubkey,
                verify=parsed.verify,
            )

    elif parsed.subcommand == "check":
        parser.error("Not implemented")

    elif parsed.subcommand == "apply":
        # Check for invalid combinations
        if "nonbooted" in parsed.type and ("a" in parsed.type or "b" in parsed.type):
            parser.error("Cannot specify 'nonbooted' and 'a' or 'b' at the same time")
        ostar_required = "a" in parsed.type or "b" in parsed.type or "nonbooted" in parsed.type
        if ostar_required and not parsed.ostar:
            parser.error("Must specify --ostar when applying ostar updates")
        if "efisys" in parsed.type and not parsed.esptar:
            parser.error("Must specify --esptar when applying efisys updates")
        apply_updates(
            filesystems,
            parsed.type,
            ostar=parsed.ostar,
            esptar=parsed.esptar,
            verify=parsed.verify,
            pubkey=parsed.pubkey,
            no_update_default_boot_label=parsed.no_grubusb,
            default_boot_label=parsed.default_boot_label,
        )

    elif parsed.subcommand == "set-default":
        with filesystems.efisys.mount(writable=True):
            write_grub_cfg_carefully(filesystems, filesystems.efisys.mountpoint, parsed.label)

    else:
        parser.error(f"Unknown subcommand {parsed.subcommand}")


def main():
    return broken_pipe_handler(main_implementation, *sys.argv)
