"""Command-line scripts (and helpers)"""

import logging
import logging.handlers
import os
import pdb
import sys
import traceback
from collections.abc import Callable
from io import StringIO
from typing import Dict, List

import yaml

from progfiguration import logger


"""Log levels that our command-line programs can configure"""
progfiguration_log_levels = [
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


class ProgfigurationTerminalError(Exception):
    """A terminal error that can be used to print a nice message"""

    def __init__(self, message, returncode):
        super().__init__(message)
        self.returncode = returncode


def progfiguration_error_handler(func: Callable[[List[str]], int], *arguments: List[str]) -> int:
    """Special error handler

    Wrap the main() function in this to properly handle the following cases:

    * Broken pipes.
      The EPIPE signal is sent if you run e.g. `script.py | head`.
      Wrapping the main function with this one exits cleanly if that happens.
      See <https://docs.python.org/3/library/signal.html#note-on-sigpipe>
    * Errors with ProgfigurationTerminalError
      These errors are intended to display nice messages to the user.
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
    except ProgfigurationTerminalError as pte:
        print(pte.message)
        sys.exit(pte.returncode)

    return returncode


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


def syslog_excepthook(type, value, tb):
    """Send an unhandled exception to syslog"""
    # Note that format_exception() returns
    # "a list of strings, each ending in a newline and some containing internal newlines"
    # <https://docs.python.org/3/library/traceback.html#traceback.format_exception>
    exc = "".join(traceback.format_exception(type, value, tb))
    logger.error(f"Encountered unhandled exception and must exit :(")
    for line in exc.splitlines():
        logger.error(line)


def configure_logging(log_stderr, log_syslog):
    if log_stderr != "NONE":
        handler_stderr = logging.StreamHandler()
        handler_stderr.setFormatter(logging.Formatter("[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"))
        handler_stderr.setLevel(log_stderr)
        logger.addHandler(handler_stderr)
    if log_syslog != "NONE":
        if not os.path.exists("/dev/log"):
            raise FileNotFoundError("There is no /dev/log on this system, cannot configure syslog logger")
        handler_syslog = logging.handlers.SysLogHandler(address="/dev/log")
        handler_syslog.setLevel(log_syslog)
        logger.addHandler(handler_syslog)


def yaml_dump_str(data, yaml_dump_kwargs: Dict) -> str:
    """Get YAML string from data

    Like yaml.dump() except it doesn't save to a file
    """
    string_stream = StringIO()
    yaml.dump(data, string_stream, **yaml_dump_kwargs)
    yaml_document_string = string_stream.getvalue()
    string_stream.close()
    return yaml_document_string
