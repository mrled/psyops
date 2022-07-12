#!/usr/bin/env python3


import argparse
import json
import logging.handlers
import re
import subprocess
import sys

from progfiguration.cli import broken_pipe_handler, configure_logging, idb_excepthook, progfiguration_log_levels


def main(*arguments):
    parser = argparse.ArgumentParser("Update psyopsOS boot media")
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Open the debugger if an unhandled exception is encountered",
    )
    parser.add_argument(
        "--log-stderr",
        default="NOTSET",
        choices=progfiguration_log_levels,
        help="Log level to send to stderr. Defaults to NOTSET (all messages, including debug). NONE to disable.",
    )
    parser.add_argument(
        "--log-syslog",
        default="INFO",
        choices=progfiguration_log_levels,
        help="Log level to send to syslog. Defaults to INFO. NONE to disable.",
    )
    parser.add_argument(
        "--progress", help="Show dd progress (requires GNU dd)", action='store_true',
    )

    parser.add_argument("isopath", help="The path to a new ISO image containing psyopsOS")

    parsed = parser.parse_args(arguments[1:])

    if parsed.debug:
        sys.excepthook = idb_excepthook
    configure_logging(parsed.log_stderr, parsed.log_syslog)

    lsblk_proc = subprocess.run(["lsblk", "--output", "PATH,LABEL,MOUNTPOINT", "--json"], check=True, capture_output=True)
    lsblk = json.loads(lsblk_proc.stdout)

    bootmedia = None
    for device in lsblk['blockdevices']:
        # Look for the iso9660 volume ID that starts with psyopsos-boot.
        # This value is set in our override in mkimage.zzz-overrides.sh.
        label = device.get("label", "") or ""
        if not label.startswith("psyopsos-boot"):
            continue

        # Make sure we find the main device, not a partition.
        # If the USB drive is /dev/sdq, then lsblk will see that both /dev/sdq and /dev/sdq1 have our volume ID.
        devpath = device.get("path", "") or ""
        if not devpath or not re.match(f'^/dev/[a-zA-Z]+$', devpath):
            continue

        bootmedia = device

    if not bootmedia:
        raise Exception(f"Could not find boot media, maybe it isn't mounted?")

    mtpt_modloop = subprocess.run(f"mountpoint /.modloop", shell=True, check=False, capture_output=True)
    if mtpt_modloop.returncode == 0:
        subprocess.run(f"umount /.modloop", shell=True, check=True)

    if bootmedia['mountpoint']:
        subprocess.run(f"umount {bootmedia['mountpoint']}", shell=True, check=True)

    ddcmd = ["dd"]
    if parsed.progress:
        ddcmd += ["status=progress"]
    ddcmd += [f"if={parsed.isopath}", f"of={bootmedia['path']}"]
    subprocess.run(ddcmd, check=True)


def wrapped_main():
    broken_pipe_handler(main, *sys.argv)
