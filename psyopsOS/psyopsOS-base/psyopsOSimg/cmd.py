"""The psyopsOSimg command

This command is deployed to nodes so that they can update their own OS.
"""


import argparse
import logging
import os
import pdb
import sys
import traceback
from typing import Callable, List

from psyopsOSimg import logger
from psyopsOSimg.grubimg import write_grubusb_nonbooted_side
from psyopsOSimg.isoimg import overwrite_iso_bootmedia


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


def main(*arguments):
    parser = argparse.ArgumentParser("Update psyopsOS boot media")
    parser.add_argument(
        "--debug", "-d", help="Drop into pdb on exception", action="store_true"
    )
    parser.add_argument("--verbose", "-v", help="Verbose logging", action="store_true")
    subparsers = parser.add_subparsers(
        dest="subcommand", help="Subcommand to run", required=True
    )
    sub_iso = subparsers.add_parser("iso", help="Update an ISO image")
    sub_iso.add_argument(
        "--no-progress",
        help="By default, it shows progress, which requires coreutils dd. With this flag, BusyBox dd will work instead, but you will get no progress as the file is written.",
        action="store_true",
    )
    sub_iso.add_argument(
        "isopath", help="The path to a new ISO image containing psyopsOS"
    )
    sub_grubusb = subparsers.add_parser(
        "grubusb", help="Write to the non-booted side of a grubusb device (A/B updates)"
    )
    sub_grubusb.add_argument(
        "tarball", help="The path to a new tarball containing psyopsOS"
    )
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

    if parsed.subcommand == "iso":
        overwrite_iso_bootmedia(parsed.isopath, not parsed.no_progress)
    elif parsed.subcommand == "grubusb":
        write_grubusb_nonbooted_side(parsed.tarball)
    else:
        parser.error(f"Unknown subcommand {parsed.subcommand}")
