"""The psyopsOSimg command

This command is deployed to nodes so that they can update their own OS.
"""

import argparse
import logging
import os
import pdb
import sys
import textwrap
import traceback
from typing import Callable, List

from neuralupgrade import logger

from neuralupgrade.downloader import download_repository_file, download_update, download_update_signature
from neuralupgrade.filesystems import Filesystem, Filesystems
from neuralupgrade.grub_cfg import write_grub_cfg_carefully
from neuralupgrade.osupdates import apply_updates, parse_trusted_comment, show_booted


def display_dict(d, indent=0, indent_step=4):
    """Recursively display a dictionary with indentation and wrapping to the terminal.

    Optimized for a compact representation of update metadata.
    If dict values are also dicts, print the key with indentation and then recursively print the dict.
    """
    try:
        terminal_width = os.get_terminal_size().columns
    except OSError:
        terminal_width = 80
    wrapper = textwrap.TextWrapper(width=terminal_width)
    for key, value in d.items():
        if isinstance(value, dict):
            # Print the key with indentation and then recursively print the dict
            print(" " * indent + str(key) + ":")
            display_dict(value, indent + indent_step, indent_step)
        else:
            # For other types, print the key and value on the same line, with wrapping if necessary
            initial_indent = " " * indent + str(key) + ": "
            subsequent_indent = " " * (indent + indent_step)
            wrapper.initial_indent = initial_indent
            wrapper.subsequent_indent = subsequent_indent
            wrapped_text = wrapper.fill(str(value))
            print(wrapped_text)


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
    verify_group = parser.add_argument_group("Verification options")
    verify_group.add_argument(
        "--no-verify", dest="verify", action="store_false", help="Skip verification of the ostar tarball"
    )
    verify_group.add_argument(
        "--pubkey",
        default="/etc/psyopsOS/minisign.pubkey",
        help="Public key to use for verification (default: %(default)s)",
    )

    # device/mountpoint override options
    overrides_group = parser.add_argument_group("Device/mountpoint override options")
    overrides_group.add_argument(
        "--efisys-dev", help="Override device for EFI system partition (found by label by default)"
    )
    overrides_group.add_argument(
        "--efisys-mountpoint", help="Override mountpoint for EFI system partition (found by label in fstab by default)"
    )
    overrides_group.add_argument(
        "--efisys-label", default="PSYOPSOSEFI", help="Override label for EFI system partition, default: %(default)s"
    )
    overrides_group.add_argument("--a-dev", help="Override device for A side (found by label by default)")
    overrides_group.add_argument(
        "--a-mountpoint", help="Override mountpoint for A side (found by label in fstab by default)"
    )
    overrides_group.add_argument(
        "--a-label", default="psyopsOS-A", help="Override label for A side, default: %(default)s"
    )
    overrides_group.add_argument("--b-dev", help="Override device for B side (found by label by default)")
    overrides_group.add_argument(
        "--b-mountpoint", help="Override mountpoint for B side (found by label in fstab by default)"
    )
    overrides_group.add_argument(
        "--b-label", default="psyopsOS-B", help="Override label for B side, default: %(default)s"
    )

    # Repository options
    repository_group = parser.add_argument_group("Repository options")
    repository_group.add_argument(
        "--repository",
        default="https://psyops.micahrl.com/os",
        help="URL for the psyopsOS update repository, default: %(default)s",
    )
    repository_group.add_argument(
        "--psyopsOS-filename-format",
        default="psyopsOS.grubusb.os.{version}.tar",
        help="The format string for the versioned grubusb EFI system partition tarfile. Used as the base for the filename in S3, and also of the signature file.",
    )
    repository_group.add_argument(
        "--psyopsESP-filename-format",
        default="psyopsOS.grubusb.efisys.{version}.tar",
        help="The format string for the versioned grubusb OS tarfile. Used as the base for the filename in S3, and also of the signature file.",
    )

    # neuralupgrade show
    show_parser = subparsers.add_parser(
        "show",
        help="Show information about the running system and/or updates. By default shows running system information.",
    )

    target_options = {
        "Literal string 'system'": "Show information about the running system",
        "Literal string 'latest'": "Show information about the latest version of psyopsOS and psyopsESP in the repository",
        "Repository filename": "Show information about an update with this filename in the repository, like 'psyopsOS.grubusb.efisys.20240208-210341.tar'. If the filename doesn't end with .minisig, append it. If the update doesn't exist, raise an error.",
        "Local path": "Show information about an update at this path, like '/path/to/update.tar.minisig'. If the filename doesn't end with .minisig, append it. If the update doesn't exist, raise an error. Local paths are checked before the repository.",
    }

    class TargetHelpAction(argparse.Action):
        """An argparse action that prints the target options help text and exits

        Nicely format each stage and its description, wrap the text to terminal width, and indent any description that is longer than one line.
        """

        def __call__(self, parser, namespace, values, option_string=None):
            terminal_width = os.get_terminal_size().columns
            max_stage_length = max(len(stage) for stage in target_options)
            lines = ["Valid targets", ""]
            for stage, desc in target_options.items():
                # Format the line with a fixed tab stop
                line = f"{stage.ljust(max_stage_length + 4)}{desc}"
                wrapped_line = textwrap.fill(line, width=terminal_width, subsequent_indent=" " * (max_stage_length + 4))
                lines.append(wrapped_line)
            lines += ["", "If multiple targets are passed, show information about each one in order.", ""]
            print("\n".join(lines))
            parser.exit()

    show_parser.add_argument(
        "target",
        default=["system"],
        nargs="*",
        help="What to show information about. Defaults to showing information about the running system. See --list-targets for more information.",
    )
    show_parser.add_argument(
        "--list-targets",
        nargs=0,
        action=TargetHelpAction,
        help="List the available targets for the 'show' subcommand",
    )

    # neuralupgrade download
    download_parser = subparsers.add_parser("download", help="Download updates")
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
    apply_parser = subparsers.add_parser("apply", help="Apply psyopsOS or EFI system partition updates")
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
    set_default_parser = subparsers.add_parser("set-default", help="Set the default boot label in the grubusb config")
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
        metadata = {}
        for target in parsed.target:
            if target == "system":
                metadata["system"] = show_booted(filesystems)
            elif target == "latest":
                os_result = download_update_signature(parsed.repository, parsed.psyopsOS_filename_format, "latest")
                esp_result = download_update_signature(parsed.repository, parsed.psyopsESP_filename_format, "latest")
                metadata["latest"] = {
                    os_result.url: os_result.unverified_metadata,
                    esp_result.url: esp_result.unverified_metadata,
                }
            else:
                if not target.endswith(".minisig"):
                    target += ".minisig"
                if os.path.exists(target):
                    target_path = os.path.abspath(target)
                    metadata[target_path] = parse_trusted_comment(sigfile=target_path)
                else:
                    try:
                        target_sig = download_repository_file(parsed.repository, target)
                        metadata[target] = parse_trusted_comment(sigcontents=target_sig)
                    except Exception:
                        parser.error(f"Target {target} does not exist")
        display_dict(metadata)

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
