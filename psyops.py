#!/usr/bin/env python3

"""PSYOPS Docker wrapper to make life a bit easier"""

import argparse
import base64
import configparser
import logging
import os
import subprocess
import sys
import textwrap


MIN_PYTHON = (3, 6)
if sys.version_info < MIN_PYTHON:
    print("This script requires Python version %.%" % MIN_PYTHON)
    sys.exit(1)


SCRIPTPATH = os.path.realpath(__file__)
SCRIPTDIR = os.path.dirname(SCRIPTPATH)
DOCKERDIR = os.path.join(SCRIPTDIR, 'docker')
logger = logging.getLogger(__name__)  # pylint: disable=C0103


def resolvepath(path):
    """Resolve a path"""
    return os.path.realpath(os.path.normpath(os.path.expanduser(path)))


def debugexchandler(exc_type, exc_value, exc_traceback):
    """Debug Exception Handler

    If sys.excepthook is set to this function, automatically enter the debugger when encountering
    an uncaught exception
    """
    if hasattr(sys, 'ps1') or not sys.stderr.isatty():
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
        imagename, imagetag, psyopsvol, tmpfsmount,
        runargs=None, containerargs=None, psyopsvolperms="rw",
        # Note: default tmpfs options are read only and noexec
        tmpfsopts="exec,mode=1777", hostname="PSYOPS"):
    """Run the Docker container"""

    # On Windows, we need to set the MSYS_NO_PATHCONV flag to 1, or else volume
    # mounting fails with weird errors
    # https://lmonkiewicz.com/programming/get-noticed-2017/docker-problems-on-windows/
    env = os.environ.copy()
    if sys.platform == 'win32':
        env['MSYS_NO_PATHCONV'] = "1"

    runcli = [
        'docker', 'run',
        '--rm',
        '--interactive',
        '--tty',
        '--volume', f'{SCRIPTDIR}:{psyopsvol}:{psyopsvolperms}',
        '--tmpfs', f'{tmpfsmount}:{tmpfsopts}',
        '--hostname', hostname]
    if runargs:
        runcli += runargs.split(" ")
    runcli += [f'{imagename}:{imagetag}']
    if containerargs:
        runcli += containerargs.split(" ")
    logger.info(f"Running an image with: {' '.join(runcli)}")
    retcode = subprocess.call(runcli, env=env)

    suppressed_result_codes = [
        130,  # probably SIGINT aka ctrl-c from the last program
    ]
    logger.info(f"'docker run' command exited with code '{retcode}'")
    if retcode > 0 and retcode not in suppressed_result_codes:
        raise Exception(f"'docker run' command exited with nonzero code '{retcode}'")


def dockerbuild(imagename, imagetag, buildargs=None):
    """Build the Docker container"""
    buildcli = [
        'docker', 'build', DOCKERDIR, '--tag', f'{imagename}:{imagetag}']
    if buildargs:
        buildcli += buildargs.split(" ")
    logger.info(f"Building an image with:\n{buildcli}")
    subprocess.check_call(buildcli)


class GitRepoMetadata():
    """Metadata of a checked-out Git repository"""

    _submodules = None

    def __init__(self, checkoutdir, dotgitdir=None):
        self.checkoutdir = checkoutdir
        if dotgitdir:
            self.dotgitdir = dotgitdir
        else:
            self.dotgitdir = os.path.join(checkoutdir, '.git')

    @property
    def submodules(self):
        """Enumerate Git submodules

        Given the checkout dir of parent Git repository, enumerate all
        submodules
        """

        if self._submodules is None:
            modconfig = configparser.ConfigParser()
            # This will return an empty config object if the file doesn't exist
            modconfig.read(os.path.join(self.checkoutdir, '.gitmodules'))
            self._submodules = []
            for section in modconfig.sections():
                copath = modconfig[section]['path']
                dotgit = os.path.join(
                    self.checkoutdir, '.git', 'modules', copath)
                self._submodules += [GitRepoMetadata(copath, dotgit)]

        return self._submodules

    def fixcrlf(self):
        """Fix autocrlf in a single Git repo

        On Windows, Git defaults to enabling 'core.autocrlf', which
        translates between Windows and Unix line endings, such that the
        repository is checked out with Windows line endings, but committed
        with Unix line endings.
        However, for Unix scripts to actually run in a Unix, we need the
        Unix line endings, so we need to disable this feature on Windows.

        Note that this is DESTRUCTIVE if there are any uncommitted changes,
        so we check for those first and fail if any are present.

        checkoutdir:    the directory the repository is checked out to
        dotgitdir:      the .git directory of the parent repo, or
                        .git/modules/<module path> for submodules
        """

        logger.info(f"Fixing CRLF for module at {self.checkoutdir}")

        status = subprocess.check_output(
            ['git', 'status'], cwd=self.checkoutdir)
        if 'nothing to commit, working tree clean' not in str(status):
            msg = f"Uncommitted changes in {self.checkoutdir}"
            logger.warning(msg)
            raise Exception(msg)

        # First, change the setting
        subprocess.check_call(
            ['git', 'config', 'core.autocrlf', 'off'], cwd=self.checkoutdir)

        # Now remove the existing index and reset the repo, so that it re-
        # checks out each file in the repository without autocrlf
        os.remove(resolvepath(os.path.join(self.dotgitdir, 'index')))
        subprocess.check_call(
            ['git', 'reset', '--hard', 'HEAD'], cwd=self.checkoutdir)

    def allfixcrlf(self):
        """Fix autocrlf in a repo and all its submodules

        Note that we fix submodules first, since the main repo was likely
        handled at checkout time anyway, so it may not be necessary to clear
        any uncommitted changes and try againn
        """
        for submodule in self.submodules:
            submodule.fixcrlf()
        self.fixcrlf()

    def testcheckout(self, throw=False):
        """Test that all submodules are checked out

        If care is not taken when the initial repo is checked out, or when the
        location of a submodule has changed, it can result in an empty
        submodule checkout directory that is not detected until we attempt to
        use it. Check for that here first and fail early.
        """
        missing = []
        for submodule in self.submodules:
            if not os.path.exists(os.path.join(submodule.checkoutdir, '.git')):
                logger.warning(
                    f"Submodule at {submodule.checkoutdir} not checked out")
                missing += [submodule.checkoutdir]
        if missing and throw:
            raise Exception(
                f"These submodules are not properly checked out: {missing}")
        return missing == []


class PsyopsArgumentCollection():
    """PSYOPS argument collection

    A container for the defined arguments.
    The parser and each subparser are set as properties, allowing them to be referenced by consuming code.
    """

    def __init__(self, *args, **kwargs):

        description = textwrap.dedent("""
            Wrap Docker for PSYOPS

            Basically, Docker can be a little precious sometimes.
            This script is intended to handle some known problems for intended use
            cases in this repo:

            - The image we build assumes that this repo will be mounted as a volume
            - Volumes in Windows wont work unless $env:MSYS_NO_PATHCONV is set
            - Windows doesn't have &&, so you can't do 'docker build && docker run'

            (This script is not intended to wrap all of Docker's functionality)""")
        epilog = textwrap.dedent("""
            Note about the passthrough arguments:

            In the (likely) case that you want to pass arguments that begin with a
            dash, you may need to use an equals sign between the passthru argument
            and its value. For instance, '--build-passthru="--no-cache"'
            """)

        self.parser = argparse.ArgumentParser(
            description=description, epilog=epilog, add_help=True,
            formatter_class=argparse.RawDescriptionHelpFormatter)

        self.parser.add_argument(
            "--verbose", "-v", action="store_true", help="Print verbose messages")
        self.parser.add_argument(
            "--debug", "-d", action="store_true",
            help="Invoke debugger on exceptions. (Implies --verbose.)")

        self.dockeropts = argparse.ArgumentParser(add_help=False)
        self.dockeropts.add_argument(
            "imagename", nargs='?', default="psyops",
            help="The name of the Docker image to build. Defaults to 'psyops'.")
        self.dockeropts.add_argument(
            "imagetag", nargs='?', default="wip",
            help="The tag to use. Defaults to 'wip'. Published versions should be 'latest'.")
        self.dockeropts.add_argument(
            "--sudo", action="store_true",
            help=(
                "Pass the enablesudo=1 arg during build, and use the tag 'sudo' rather than the "
                "default when building or running. (Overrides any other tag set.)"))

        self.dockerbuildopts = argparse.ArgumentParser(add_help=False)
        self.dockerbuildopts.add_argument(
            '--build-passthru', dest='buildargs', default="",
            help="Pass these additional arguments to 'docker build'")

        self.dockerrunopts = argparse.ArgumentParser(add_help=False)
        self.dockerrunopts.add_argument(
            '--run-passthru', dest='runargs',
            help="Pass these additional arguments to 'docker run'")
        self.dockerrunopts.add_argument(
            '--container-passthru', dest='containerargs',
            help="Pass these additional arguments to the container itself")
        self.dockerrunopts.add_argument(
            '--psyops-volume', dest='psyopsvol', default="/psyops",
            help="Mount point for the psyops volume")
        self.dockerrunopts.add_argument(
            '--secrets-tmpfs', dest='secretstmpfs', default="/secrets",
            help="Mount point for the secrets tmpfs filesystem")

        self.utilopts = argparse.ArgumentParser(add_help=False)
        self.utilsubparsers = self.utilopts.add_subparsers(dest="utilaction")
        self.utilsubparsers.required = True
        self.utilsubparsers.add_parser(
            'enumsubmod', help='List all Git submodules')
        self.utilsubparsers.add_parser(
            'fixcrlf', help='Disasble core.autocrlf on parent repo and all submodules')

        self.subparsers = self.parser.add_subparsers(dest="action")
        self.subparsers.required = True
        self.subparsers.add_parser(
            'build', parents=[self.dockeropts, self.dockerbuildopts],
            help='Build the Docker image')
        self.subparsers.add_parser(
            'run', parents=[self.dockeropts, self.dockerrunopts],
            help='Run the Docker image')
        self.subparsers.add_parser(
            'buildrun', parents=[self.dockeropts, self.dockerbuildopts, self.dockerrunopts],
            help='Build the Docker image, then immediately run it')
        self.subparsers.add_parser(
            'util', parents=[self.utilopts],
            help='Utility functions')

        self.parsed = self.parser.parse_args(*args, **kwargs)


def main(*args, **kwargs):  # pylint: disable=W0613
    """PSYOPS Docker wrapper main program execution"""

    arguments = PsyopsArgumentCollection()
    parsed = arguments.parsed

    if parsed.verbose or parsed.debug:
        logger.setLevel(logging.DEBUG)
    if parsed.debug:
        sys.excepthook = debugexchandler

    logger.info(parsed)

    parentrepo = GitRepoMetadata(SCRIPTDIR)

    if 'sudo' in parsed and parsed.sudo:
        if 'buildargs' in parsed:
            parsed.buildargs += "--build-arg enablesudo=1"
        parsed.imagetag = "sudo"

    if parsed.action == "build":
        parentrepo.testcheckout(throw=True)
        dockerbuild(parsed.imagename, parsed.imagetag, buildargs=parsed.buildargs)
    elif parsed.action == "run":
        parentrepo.testcheckout(throw=True)
        dockerrun(
            parsed.imagename, parsed.imagetag, parsed.psyopsvol,
            parsed.secretstmpfs, runargs=parsed.runargs,
            containerargs=parsed.containerargs)
    elif parsed.action == "buildrun":
        parentrepo.testcheckout(throw=True)
        dockerbuild(parsed.imagename, parsed.imagetag, buildargs=parsed.buildargs)
        dockerrun(
            parsed.imagename, parsed.imagetag, parsed.psyopsvol,
            parsed.secretstmpfs, runargs=parsed.runargs,
            containerargs=parsed.containerargs)
    elif parsed.action == "util":
        if parsed.utilaction == 'enumsubmod':
            for submod in parentrepo.submodules:
                print(submod.checkoutdir)
        elif parsed.utilaction == 'fixcrlf':
            parentrepo.allfixcrlf()
        else:
            print(f"Unknown utilaction: '{parsed.utilaction}'")
            arguments.utilopts.print_help()
            return 1
    else:
        print(f"Unknown action '{parsed.action}'")
        arguments.parser.print_usage()
        return 1


if __name__ == '__main__':
    sys.exit(main(*sys.argv))
