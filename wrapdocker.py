#!/usr/bin/env python3

import argparse
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


def run(imagename, imagetag, runargs=None, containerargs=None):

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


def build(imagename, imagetag, buildargs=None):
    buildcli = [
        'docker', 'build', scriptdir, '--tag', f'{imagename}:{imagetag}']
    if buildargs:
        buildcli += buildargs.split(" ")
    log.info(f"Building an image with:\n{buildcli}")
    subprocess.check_call(buildcli)


def main(*args, **kwargs):
    epilog = textwrap.dedent("""
        Basically, Docker can be a little precious sometimes.
        This script is intended to handle some known problems for intended use
        cases in this repo:

        - The image we build assumes that this repo will be mounted as a volume
        - Volumes in Windows wont work unless %MSYS_NO_PATHCONV% is set
        - Windows doesn't have &&, so you can't do 'docker build && docker run'

        (This script is not intended to wrap all of Docker's functionality)""")
    parser = argparse.ArgumentParser(
        description="Wrap Docker for PSYOPS", epilog=epilog, add_help=True,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Print verbose messages")

    commonopts = argparse.ArgumentParser(add_help=False)
    commonopts.add_argument(
        "imagename", nargs='?', default="psyops",
        help="The name of the Docker image to build. Defaults to 'psyops'.")
    commonopts.add_argument(
        "imagetag", nargs='?', default="wip",
        help="The tag to use. Defaults to 'wip'. Published versions should be 'latest'.")

    buildopts = argparse.ArgumentParser(add_help=False)
    buildopts.add_argument(
        '--build-passthru', dest='buildargs',
        help="Pass these additional arguments to 'docker build'")

    runopts = argparse.ArgumentParser(add_help=False)
    runopts.add_argument(
        '--run-passthru', dest='runargs',
        help="Pass these additional arguments to 'docker run'")
    runopts.add_argument(
        '--container-passthru', dest='containerargs',
        help="Pass these additional arguments to the container itself")

    subparsers = parser.add_subparsers(dest="action")
    subparsers.add_parser('build', parents=[commonopts, buildopts])
    subparsers.add_parser('run', parents=[commonopts, runopts])
    subparsers.add_parser('buildrun', parents=[commonopts, buildopts, runopts])

    parsed = parser.parse_args()

    if parsed.verbose:
        log.setLevel(logging.DEBUG)

    log.info(parsed)

    if "build" in parsed.action:
        build(parsed.imagename, parsed.imagetag, buildargs=parsed.buildargs)
    if "run" in parsed.action:
        run(
            parsed.imagename, parsed.imagetag, runargs=parsed.runargs,
            containerargs=parsed.containerargs)


if __name__ == '__main__':
    sys.exit(main(*sys.argv))
