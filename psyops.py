#!/usr/bin/env python3

"""PSYOPS Docker wrapper to make life a bit easier"""

import argparse
import logging
import os
import subprocess
import sys
import textwrap
from types import TracebackType


SCRIPTPATH = os.path.realpath(__file__)
SCRIPTDIR = os.path.dirname(SCRIPTPATH)
DOCKERDIR = os.path.join(SCRIPTDIR, "docker")
logger = logging.getLogger(__name__)  # pylint: disable=C0103


def debugexchandler(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: TracebackType | None,
):
    """Debug Exception Handler

    If sys.excepthook is set to this function, automatically enter the debugger when encountering
    an uncaught exception
    """
    if hasattr(sys, "ps1") or not sys.stderr.isatty():
        # we are in interactive mode or we don't have a tty-like
        # device, so we call the default hook
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    else:
        import pdb
        import traceback

        # we are NOT in interactive mode, print the exception...
        traceback.print_exception(exc_type, exc_value, exc_traceback)
        print()
        # ...then start the debugger in post-mortem mode.
        pdb.pm()


def dockerrun(
    imagename: str,
    imagetag: str,
    psyopsvol: str,
    tmpfsmount: str,
    runargs: str = "",
    containerargs: str = "",
    # Note: default tmpfs options are read only and noexec
    tmpfsopts: str = "exec,mode=1777",
    hostname: str = "PSYOPS",
):
    """Run the Docker container"""
    runcli = [
        "docker",
        "run",
        "--rm",
        "--interactive",
        "--tty",
        "--volume",
        f"{SCRIPTDIR}:{psyopsvol}:rw",
        "--tmpfs",
        f"{tmpfsmount}:{tmpfsopts}",
        "--hostname",
        hostname,
        *runargs.split(" "),
        f"{imagename}:{imagetag}",
        *containerargs.split(" "),
    ]
    logger.info(f"Running an image with: {' '.join(runcli)}")
    os.execvp(runcli[0], runcli)


def dockerbuild(imagename: str, imagetag: str, additional_build_args: str = ""):
    """Build the Docker container"""

    build_time_vars_arg = ""
    if sys.platform.startswith("linux"):
        build_time_vars_arg = [
            "--build-arg",
            f"PSYOPS_UID={os.geteuid()}",
            "--build-arg",
            f"PSYOPS_GID={os.getegid()}",
        ]

    buildcli = [
        "docker",
        "build",
        *build_time_vars_arg,
        DOCKERDIR,
        "--progress",
        "plain",
        "--tag",
        f"{imagename}:{imagetag}",
        *additional_build_args.split(" "),
    ]

    logger.info(f"Building an image with:\n{buildcli}")
    subprocess.check_call(buildcli)


class PsyopsArgumentCollection:
    """PSYOPS argument collection

    A container for the defined arguments.
    The parser and each subparser are set as properties, allowing them to be referenced by consuming code.
    """

    def __init__(self, args: list[str]):

        description = "Wrap Docker for PSYOPS"
        epilog = textwrap.dedent(
            """
            Note about the passthrough arguments:

            In the (likely) case that you want to pass arguments that begin with a
            dash, you may need to use an equals sign between the passthru argument
            and its value. For instance, '--build-passthru="--no-cache"'
            """
        )

        self.parser = argparse.ArgumentParser(
            description=description,
            epilog=epilog,
            add_help=True,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )

        self.parser.add_argument(
            "--verbose", "-v", action="store_true", help="Print verbose messages"
        )
        self.parser.add_argument(
            "--debug",
            "-d",
            action="store_true",
            help="Invoke debugger on exceptions. (Implies --verbose.)",
        )

        self.dockeropts = argparse.ArgumentParser(add_help=False)
        self.dockeropts.add_argument(
            "imagename",
            nargs="?",
            default="psyops",
            help="The name of the Docker image to build. Defaults to 'psyops'.",
        )
        self.dockeropts.add_argument(
            "imagetag",
            nargs="?",
            default="wip",
            help="The tag to use. Defaults to 'wip'. Published versions should be 'latest'.",
        )

        self.dockerbuildopts = argparse.ArgumentParser(add_help=False)
        self.dockerbuildopts.add_argument(
            "--build-passthru",
            dest="buildargs",
            default="",
            help="Pass these additional arguments to 'docker build'",
        )

        self.dockerrunopts = argparse.ArgumentParser(add_help=False)
        self.dockerrunopts.add_argument(
            "--run-passthru",
            dest="runargs",
            help="Pass these additional arguments to 'docker run'",
        )
        self.dockerrunopts.add_argument(
            "--container-passthru",
            dest="containerargs",
            help="Pass these additional arguments to the container itself",
        )
        self.dockerrunopts.add_argument(
            "--psyops-volume",
            dest="psyopsvol",
            default="/psyops",
            help="Mount point for the psyops volume",
        )
        self.dockerrunopts.add_argument(
            "--secrets-tmpfs",
            dest="secretstmpfs",
            default="/secrets",
            help="Mount point for the secrets tmpfs filesystem",
        )

        self.subparsers = self.parser.add_subparsers(dest="action")
        self.subparsers.required = True
        self.subparsers.add_parser(
            "build",
            parents=[self.dockeropts, self.dockerbuildopts],
            help="Build the Docker image",
        )
        self.subparsers.add_parser(
            "run",
            parents=[self.dockeropts, self.dockerrunopts],
            help="Run the Docker image",
        )
        self.subparsers.add_parser(
            "buildrun",
            parents=[self.dockeropts, self.dockerbuildopts, self.dockerrunopts],
            help="Build the Docker image, then immediately run it",
        )

        self.parsed = self.parser.parse_args(args=args)


def main(args: list[str]):  # pylint: disable=W0613
    """PSYOPS Docker wrapper main program execution"""

    arguments = PsyopsArgumentCollection(args)
    parsed = arguments.parsed

    if parsed.verbose or parsed.debug:
        logger.setLevel(logging.DEBUG)
    if parsed.debug:
        sys.excepthook = debugexchandler

    knownaction = False
    if parsed.action in ["build", "buildrun"]:
        knownaction = True
        dockerbuild(
            parsed.imagename, parsed.imagetag, additional_build_args=parsed.buildargs
        )
    if parsed.action in ["run", "buildrun"]:
        knownaction = True
        dockerrun(
            parsed.imagename,
            parsed.imagetag,
            parsed.psyopsvol,
            parsed.secretstmpfs,
            runargs=parsed.runargs,
            containerargs=parsed.containerargs,
        )
    if not knownaction:
        print(f"Unknown action '{parsed.action}'")
        arguments.parser.print_usage()
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
