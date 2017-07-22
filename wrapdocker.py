#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys


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
    parser = argparse.ArgumentParser(
        description="Wrap Docker for PSYOPS",
        epilog="Docker can be a little precious sometimes, and Windows is clearly a second class citizen even today",
        add_help=True)
    parser.add_argument("action", choices=["build", "run"])
    parser.add_argument("imagename", nargs='?', default="psyops")
    parser.add_argument("imagetag", nargs='?', default="wip")
    parser.add_argument("--", dest="passargs", nargs=argparse.REMAINDER)
    parsed = parser.parse_args()
    if parsed.action == "build":
        build(parsed.imagename, parsed.imagetag, passargs=parsed.passargs)
    elif parsed.action == "run":
        run(parsed.imagename, parsed.imagetag, passargs=parsed.passargs)
    else:
        raise Exception()


if __name__ == '__main__':
    sys.exit(main(*sys.argv))
