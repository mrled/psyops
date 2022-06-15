"""The command line interface for progfiguration"""

import argparse
import logging
import logging.handlers
import pdb
import sys
import traceback

from progfiguration import logger
from progfiguration.facts import PsyopsOsNode
from progfiguration.roles import skunkworks


_log_levels = [
    # Levels from the library
    "CRITICAL",
    "ERROR",
    "WARNING",
    "INFO",
    "DEBUG",
    "NOTSET",
    # My customization
    "NONE",
]


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


def main():
    parser = argparse.ArgumentParser("psyopsOS programmatic configuration")
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Open the debugger if an unhandled exception is encountered",
    )
    parser.add_argument(
        "--log-stderr",
        default="NOTSET",
        choices=_log_levels,
        help="Log level to send to stderr. Defaults to NOTSET (all messages, including debug). NONE to disable.",
    )
    parser.add_argument(
        "--log-syslog",
        default="INFO",
        choices=_log_levels,
        help="Log level to send to syslog. Defaults to INFO. NONE to disable.",
    )
    parser.add_argument("nodename", help="The nodename")
    parsed = parser.parse_args()

    if parsed.debug:
        sys.excepthook = idb_excepthook

    if parsed.log_stderr != "NONE":
        handler_stderr = logging.StreamHandler()
        handler_stderr.setFormatter(
            "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"
        )
        handler_stderr.setLevel(parsed.log_stderr)
        logger.addHandler(handler_stderr)
    if parsed.log_syslog != "NONE":
        handler_syslog = logging.handlers.SysLogHandler(address="/dev/log")
        handler_syslog.setLevel(parsed.log_syslog)
        logger.addHandler(handler_syslog)

    node = PsyopsOsNode(parsed.nodename)
    skunkworks.apply(node, {})
