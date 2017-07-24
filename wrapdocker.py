#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
import textwrap


MIN_PYTHON = (3, 6)
if sys.version_info < MIN_PYTHON:
    print("This script requires Python version %.%" % MIN_PYTHON)
    sys.exit(1)


scriptdir = os.path.dirname(os.path.realpath(__file__))


def run(imagename, imagetag, passargs=None):

    # On Windows, we need to set the MSYS_NO_PATHCONV flag to 1, or else volume
    # mounting fails with weird errors
    # https://lmonkiewicz.com/programming/get-noticed-2017/docker-problems-on-windows/
    env = os.environ.copy()
    if sys.platform == 'win32':
        env['MSYS_NO_PATHCONV'] = 1

    runcli = [
        'docker', 'run',
        '--rm',
        '--interactive',
        '--tty',
        '--volume', f'{scriptdir}:/psyops:rw']
    if passargs:
        runcli += passargs
    runcli += [f'{imagename}:{imagetag}']
    subprocess.check_call(runcli, env=env)


def build(imagename, imagetag, passargs=None):
    buildcli = [
        'docker', 'build', scriptdir, '--tag', f'{imagename}:{imagetag}']
    if passargs:
        buildcli += passargs
    subprocess.check_call(buildcli)


def main(*args, **kwargs):
    epilog = textwrap.dedent("""
        Basically, Docker can be a little precious sometimes.
        This script is intended to handle some known problems for intended use
        cases in this repo:

        - The image we build assumes that this repo will be mounted as a volume
        - Volumes in Windows wont work unless %MSYS_NO_PATHCONV% is set

        (This script is not intended to wrap all of Docker's functionality)""")
    parser = argparse.ArgumentParser(
        description="Wrap Docker for PSYOPS", epilog=epilog, add_help=True,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "action", choices=["build", "run"],
        help="Docker subcommand")
    parser.add_argument(
        "imagename", nargs='?', default="psyops",
        help="The name of the Docker image to build. Defaults to 'psyops'.")
    parser.add_argument(
        "imagetag", nargs='?', default="wip",
        help="The tag to use. Defaults to 'wip'. Published versions should be 'latest'.")
    parser.add_argument(
        "--", dest="passargs", nargs=argparse.REMAINDER,
        help="Pass arguments to *Docker* (not when running the image)")
    parsed = parser.parse_args()
    if parsed.action == "build":
        build(parsed.imagename, parsed.imagetag, passargs=parsed.passargs)
    elif parsed.action == "run":
        run(parsed.imagename, parsed.imagetag, passargs=parsed.passargs)
    else:
        raise Exception()


if __name__ == '__main__':
    sys.exit(main(*sys.argv))
