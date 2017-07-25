#!/usr/bin/env python3

import argparse
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


scriptdir = os.path.dirname(os.path.realpath(__file__))


def getlogger():
    log = logging.getLogger('wrapdocker')
    log.setLevel(logging.WARNING)
    conhandler = logging.StreamHandler()
    conhandler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    log.addHandler(conhandler)
    return log


log = getlogger()


def resolvepath(path):
    return os.path.realpath(os.path.normpath(os.path.expanduser(path)))


def debugexchandler(type, value, tb):
    if hasattr(sys, 'ps1') or not sys.stderr.isatty():
        # we are in interactive mode or we don't have a tty-like
        # device, so we call the default hook
        sys.__excepthook__(type, value, tb)
    else:
        import traceback, pdb  # noqa
        # we are NOT in interactive mode, print the exception...
        traceback.print_exception(type, value, tb)
        print
        # ...then start the debugger in post-mortem mode.
        pdb.pm()


def dockerrun(imagename, imagetag, runargs=None, containerargs=None):

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
        '--volume', f'{scriptdir}:/psyops:rw']
    if runargs:
        runcli += runargs.split(" ")
    runcli += [f'{imagename}:{imagetag}']
    if containerargs:
        runcli += containerargs.split(" ")
    log.info(f"Running an image with: {' '.join(runcli)}")
    subprocess.check_call(runcli, env=env)


def dockerbuild(imagename, imagetag, buildargs=None):
    buildcli = [
        'docker', 'build', scriptdir, '--tag', f'{imagename}:{imagetag}']
    if buildargs:
        buildcli += buildargs.split(" ")
    log.info(f"Building an image with:\n{buildcli}")
    subprocess.check_call(buildcli)


class GitRepoMetadata():

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

        log.info(f"Fixing CRLF for module at {self.checkoutdir}")

        status = subprocess.check_output(
            ['git', 'status'], cwd=self.checkoutdir)
        if 'nothing to commit, working tree clean' not in str(status):
            msg = f"Uncommitted changes in {self.checkoutdir}"
            log.warning(msg)
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


def main(*args, **kwargs):
    description = textwrap.dedent("""
        Wrap Docker for PSYOPS

        Basically, Docker can be a little precious sometimes.
        This script is intended to handle some known problems for intended use
        cases in this repo:

        - The image we build assumes that this repo will be mounted as a volume
        - Volumes in Windows wont work unless %MSYS_NO_PATHCONV% is set
        - Windows doesn't have &&, so you can't do 'docker build && docker run'

        (This script is not intended to wrap all of Docker's functionality)""")
    epilog = textwrap.dedent("""
        Note about the passthrough arguments:

        In the (likely) case that you want to pass arguments that begin with a
        dash, you may need to use an equals sign between the passthru argument
        and its value. For instance, '--build-passthru="--no-cache"'
        """)
    parser = argparse.ArgumentParser(
        description=description, epilog=epilog, add_help=True,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print verbose messages")
    parser.add_argument(
        "--debug", "-d", action="store_true",
        help="Invoke debugger on exceptions. (Implies --verbose.)")

    dockeropts = argparse.ArgumentParser(add_help=False)
    dockeropts.add_argument(
        "imagename", nargs='?', default="psyops",
        help="The name of the Docker image to build. Defaults to 'psyops'.")
    dockeropts.add_argument(
        "imagetag", nargs='?', default="wip",
        help="The tag to use. Defaults to 'wip'. Published versions should be 'latest'.")

    dockerbuildopts = argparse.ArgumentParser(add_help=False)
    dockerbuildopts.add_argument(
        '--build-passthru', dest='buildargs',
        help="Pass these additional arguments to 'docker build'")

    dockerrunopts = argparse.ArgumentParser(add_help=False)
    dockerrunopts.add_argument(
        '--run-passthru', dest='runargs',
        help="Pass these additional arguments to 'docker run'")
    dockerrunopts.add_argument(
        '--container-passthru', dest='containerargs',
        help="Pass these additional arguments to the container itself")

    repoopts = argparse.ArgumentParser(add_help=False)
    repoopts.add_argument(
        'repoaction', choices=['enumsubmod', 'fixcrlf'],
        help="Operate on the Git repository and submodules. If 'enumsubmod', list all submodules. If 'fixcrlf', disable core.autocrlf on parent repo and all submodules.")

    subparsers = parser.add_subparsers(dest="action")
    subparsers.add_parser(
        'build', parents=[dockeropts, dockerbuildopts])
    subparsers.add_parser(
        'run', parents=[dockeropts, dockerrunopts])
    subparsers.add_parser(
        'buildrun', parents=[dockeropts, dockerbuildopts, dockerrunopts])
    subparsers.add_parser(
        'repo', parents=[repoopts])

    parsed = parser.parse_args()

    if parsed.verbose or parsed.debug:
        log.setLevel(logging.DEBUG)
    if parsed.debug:
        sys.excepthook = debugexchandler

    log.info(parsed)

    if parsed.action == "build":
        dockerbuild(parsed.imagename, parsed.imagetag, buildargs=parsed.buildargs)
    elif parsed.action == "run":
        dockerrun(
            parsed.imagename, parsed.imagetag, runargs=parsed.runargs,
            containerargs=parsed.containerargs)
    elif parsed.action == "buildrun":
        dockerbuild(parsed.imagename, parsed.imagetag, buildargs=parsed.buildargs)
        dockerrun(
            parsed.imagename, parsed.imagetag, runargs=parsed.runargs,
            containerargs=parsed.containerargs)
    elif parsed.action == "repo":
        parentrepo = GitRepoMetadata(scriptdir)
        if "enumsubmod" in parsed.repoaction:
            for submod in parentrepo.submodules:
                print(submod.checkoutdir)
        elif "fixcrlf" in parsed.repoaction:
            parentrepo.allfixcrlf()
    else:
        parser.print_usage()
        return 1


if __name__ == '__main__':
    sys.exit(main(*sys.argv))
