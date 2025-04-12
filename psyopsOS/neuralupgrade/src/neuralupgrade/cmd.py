"""The neuralupgrade command

This command is deployed to nodes so that they can update their own OS.
"""

import argparse
import logging
import os
import pdb
import platform
import sys
import textwrap
import traceback
from typing import Callable, List

from neuralupgrade import dictify, logger

from neuralupgrade.coginitivedefects import MultiError
from neuralupgrade.downloader import download_repository_file, download_update, download_update_signature
from neuralupgrade.filesystems import Filesystem, Filesystems
from neuralupgrade.grub_cfg import write_grub_cfg_carefully
from neuralupgrade.osupdates import apply_updates, check_updates, get_system_metadata
from neuralupgrade.update_metadata import parse_trusted_comment


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
        print("")
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


def subcommand_show(parsed: argparse.Namespace, parser: argparse.ArgumentParser, filesystems: Filesystems):
    metadata = {}
    for target in parsed.target:
        if target == "system":
            metadata["system"] = dictify.dictify(get_system_metadata(filesystems))
        elif target == "latest":
            os_result = download_update_signature(
                parsed.repository, parsed.psyopsOS_filename_format, parsed.architecture, "latest"
            )
            esp_result = download_update_signature(
                parsed.repository, parsed.psyopsESP_filename_format, parsed.architecture, "latest"
            )
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


def subcommand_apply(parsed: argparse.Namespace, parser: argparse.ArgumentParser, filesystems: Filesystems):
    # Check for invalid combinations
    if "nonbooted" in parsed.target and ("a" in parsed.target or "b" in parsed.target):
        parser.error("Cannot specify 'nonbooted' and 'a' or 'b' at the same time")
    updating_os = "a" in parsed.target or "b" in parsed.target or "nonbooted" in parsed.target
    updating_esp = "efisys" in parsed.target
    os_tar = ""
    esp_tar = ""
    os_tar_downloaded = False
    esp_tar_downloaded = False
    update_err = None
    try:
        if updating_os:
            if parsed.os_tar:
                os_tar = parsed.os_tar
            elif parsed.os_version:
                os_tar = download_update(
                    parsed.repository,
                    parsed.psyopsOS_filename_format,
                    parsed.architecture,
                    parsed.os_version,
                    parsed.update_tmpdir,
                    pubkey=parsed.pubkey,
                    verify=parsed.verify,
                )
                os_tar_downloaded = True
            else:
                parser.error("Must specify --os-tar or --os-version when applying os updates")
        if updating_esp:
            if parsed.esp_tar:
                esp_tar = parsed.esp_tar
            elif parsed.esp_version:
                esp_tar = download_update(
                    parsed.repository,
                    parsed.psyopsESP_filename_format,
                    parsed.architecture,
                    parsed.esp_version,
                    parsed.update_tmpdir,
                    pubkey=parsed.pubkey,
                    verify=parsed.verify,
                )
                esp_tar_downloaded = True
            else:
                parser.error("Must specify --esp-tar or --esp-version when applying efisys updates")
        apply_updates(
            filesystems,
            parsed.target,
            ostar=os_tar,
            esptar=esp_tar,
            verify=parsed.verify,
            pubkey=parsed.pubkey,
            no_update_default_boot_label=parsed.no_grub_cfg,
            default_boot_label=parsed.default_boot_label,
        )
    except Exception as exc:
        update_err = exc
    finally:
        cleanup_errs = []
        try:
            if os_tar_downloaded:
                os.remove(os_tar)
        except Exception as e:
            cleanup_errs.append(e)
        try:
            if esp_tar_downloaded:
                os.remove(esp_tar)
        except Exception as e:
            cleanup_errs.append(e)

        if cleanup_errs:
            cleanup_msg = f"Encountered errors cleaning up downloaded updates: {cleanup_errs}"
            if update_err:
                raise MultiError(cleanup_msg, cleanup_errs) from update_err
            raise MultiError(cleanup_msg, cleanup_errs)
        elif update_err:
            raise update_err


def subcommand_download(parsed: argparse.Namespace, parser: argparse.ArgumentParser):
    output: str = parsed.output
    if len(parsed.type) > 1 and not output.endswith("/"):
        output += "/"
    if "psyopsOS" in parsed.type:
        download_update(
            parsed.repository,
            parsed.psyopsOS_filename_format,
            parsed.architecture,
            parsed.version,
            output,
            pubkey=parsed.pubkey,
            verify=parsed.verify,
        )
    if "psyopsESP" in parsed.type:
        download_update(
            parsed.repository,
            parsed.psyopsESP_filename_format,
            parsed.architecture,
            parsed.version,
            output,
            pubkey=parsed.pubkey,
            verify=parsed.verify,
        )


def subcommand_check(parsed: argparse.Namespace, parser: argparse.ArgumentParser, filesystems: Filesystems):
    checked = check_updates(
        filesystems,
        parsed.target,
        parsed.version,
        parsed.repository,
        parsed.psyopsOS_filename_format,
        parsed.psyopsESP_filename_format,
        parsed.architecture,
    )
    for fs, fsmd in checked.items():
        if fsmd["up_to_date"]:
            print(f"{fs}: {fsmd['label']} is version {fsmd['compared_to']}")
        else:
            print(
                f"{fs}: {fsmd['label']} is currently version {fsmd['current_version']}, not version {fsmd['compared_to']}"
            )


def getparser(prog=None) -> argparse.ArgumentParser:
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
    overrides_group.add_argument("--update-tmpdir", default="/tmp", help="Temporary directory for update downloads")

    # Repository options
    repository_group = parser.add_argument_group("Repository options")
    repository_group.add_argument(
        "--architecture",
        # This is whatever `uname -m` says, like x86_64.
        default=platform.machine(),
        help="Architecture for the update, default is whatever `uname -m` says: %(default)s. WARNING: NO VERIFICATION IS DONE TO ENSURE THIS MATCHES THE ACTUAL ARCHITECTURE OF THE UPDATE. USE WITH CAUTION.",
    )
    repository_group.add_argument(
        "--repository",
        default="https://psyops.micahrl.com/os",
        help="URL for the psyopsOS update repository, default: %(default)s",
    )
    repository_group.add_argument(
        "--psyopsOS-filename-format",
        default="psyopsOS.{architecture}.{version}.tar",
        help="The format string for the versioned psyopsESP tarfile. Used as the base for the filename in S3, and also of the signature file.",
    )
    repository_group.add_argument(
        "--psyopsESP-filename-format",
        default="psyopsESP.{architecture}.{version}.tar",
        help="The format string for the versioned psyopsOS tarfile. Used as the base for the filename in S3, and also of the signature file.",
    )

    # neuralupgrade show
    show_parser = subparsers.add_parser(
        "show",
        help="Show information about the running system and/or updates. By default shows running system information.",
    )

    target_options = {
        "Literal string 'system'": "Show information about the running system",
        "Literal string 'latest'": "Show information about the latest version of psyopsOS and psyopsESP in the repository",
        "Repository filename": "Show information about an update with this filename in the repository, like 'psyopsOS.20240208-210341.tar'. If the filename doesn't end with .minisig, append it. If the update doesn't exist, raise an error.",
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

    # neuralupgrade check
    check_parser = subparsers.add_parser("check", help="Check whether the running system is up to date")
    check_parser.add_argument(
        "--version", default="latest", help="Version of the update to check, default: %(default)s"
    )
    check_parser.add_argument(
        "--target",
        default=["nonbooted", "efisys"],
        nargs="+",
        choices=["a", "b", "nonbooted", "efisys"],
        help="The target filesystem(s) to check",
    )

    # neuralupgrade apply
    apply_parser = subparsers.add_parser("apply", help="Apply psyopsOS or EFI system partition updates")
    apply_parser.add_argument(
        "target", nargs="+", choices=["a", "b", "nonbooted", "efisys"], help="The target(s) to apply updates to"
    )
    apply_parser.add_argument(
        "--default-boot-label",
        dest="default_boot_label",
        help="Default boot label if writing the grub.cfg file",
    )
    apply_parser.add_argument(
        "--no-grub-cfg",
        action="store_true",
        help="Skip updating the grub.cfg file (only applies when target includes nonbooted)",
    )
    os_update_group = apply_parser.add_mutually_exclusive_group()
    os_update_group.add_argument("--os-tar", help="A local path to a psyopsOS tarball to apply")
    os_update_group.add_argument("--os-version", help="A version in the remote repository to apply")
    esp_update_group = apply_parser.add_mutually_exclusive_group()
    esp_update_group.add_argument("--esp-tar", help="A local path to an efisys tarball to apply")
    esp_update_group.add_argument("--esp-version", help="A version in the remote repository to apply")

    # neuralupgrade set-default
    set_default_parser = subparsers.add_parser("set-default", help="Set the default boot label in the grub.cfg file")
    set_default_parser.add_argument("label", help="The label to set as the default boot label")

    return parser


def main_implementation(arguments: list[str]) -> int:
    parser = getparser()
    parsed = parser.parse_args(arguments[1:])

    conhandler = logging.StreamHandler()
    formatter = logging.Formatter("%(name)s %(levelname)s %(message)s")
    conhandler.setFormatter(formatter)
    logger.addHandler(conhandler)
    logger.setLevel(logging.INFO)
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

    if not parsed.update_tmpdir.endswith("/"):
        parsed.update_tmpdir += "/"

    if parsed.subcommand == "show":
        subcommand_show(parsed, parser, filesystems)
    elif parsed.subcommand == "download":
        subcommand_download(parsed, parser)
    elif parsed.subcommand == "check":
        subcommand_check(parsed, parser, filesystems)
    elif parsed.subcommand == "apply":
        subcommand_apply(parsed, parser, filesystems)
    elif parsed.subcommand == "set-default":
        with filesystems.efisys.mount(writable=True):
            write_grub_cfg_carefully(filesystems, filesystems.efisys.mountpoint, parsed.label)
    else:
        parser.error(f"Unknown subcommand {parsed.subcommand}")

    return 0


def main():
    return broken_pipe_handler(main_implementation, sys.argv)
