import argparse
import json
import os
import subprocess
import sys
from typing import Dict, List

from progfiguration.cli import (
    ProgfigurationTerminalError,
    progfiguration_error_handler,
    configure_logging,
    idb_excepthook,
    progfiguration_log_levels,
)


def lsblk(device: str) -> Dict:
    """Run lsblk on a device"""
    result = subprocess.run(["lsblk", "--json", device], check=True, capture_output=True)
    output = json.loads(result.stdout)
    return output


def resolve_disk(s: str) -> str:
    """Find the full path for a disk.

    Given a string representing a device, check if it exists as a direct path, a path under /dev/mapper, or a path under /dev
    """
    maybes = [
        s,
        f"/dev/mapper/{s}",
        f"/dev/{s}",
    ]
    for maybe in maybes:
        if os.path.exists(maybe):
            return maybe
    raise FileNotFoundError(f"Could not find device with name {s}")


def wipe(disks: List[str]):
    for disk in disks:
        disk_path = resolve_disk(disk)
        blk = lsblk(disk_path)
        for found_device in blk["blockdevices"]:
            children = found_device.get("children", [])
            for child in children:
                wipe(child)

            for mp in [m for m in child["mountpoints"] if m]:
                try:
                    subprocess.run(["umount", mp], check=True)
                except subprocess.CalledProcessError:
                    raise ProgfigurationTerminalError(f"Could not unmount {child['name']} from mountpoint {mp}", 1)

            # Unfortunately lsblk's "name" field for a device doesn't include the full path, smh
            found_device_path = resolve_disk(found_device["name"])

            if found_device["type"] == "disk":
                subprocess.run(["wipefs", "--all", found_device_path], check=True)
            elif found_device["type"] == "part":
                subprocess.run(["wipefs", "--all", found_device_path], check=True)
            elif found_device["type"] == "crypt":
                subprocess.run(["cryptsetup", "close", found_device["name"]], check=True)
            elif found_device["type"] == "lvm":
                raise Exception("lol, we don't handle lvm yet")
            else:
                raise Exception(f"Unknown type {found_device['type']} for device {found_device['name']}.")


def parseargs(arguments: List[str]):
    parser = argparse.ArgumentParser("psyopsOS progfiguration disk wipe. VERY EXPERIMENTAL.")
    parser.add_argument(
        "--debug", "-d", action="store_true", help="Open the debugger if an unhandled exception is encountered"
    )
    parser.add_argument("--force", "-f", action="store_true", help="Skip verification prompts")
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
        "disk",
        nargs="+",
        help="List of block devices to wipe, as direct paths, paths under /dev/mapper, or paths under /dev, checked in that order",
    )

    parsed = parser.parse_args(arguments)
    return parser, parsed


def main_implementation(*arguments):
    parser, parsed = parseargs(arguments[1:])

    if parsed.debug:
        sys.excepthook = idb_excepthook
    configure_logging(parsed.log_stderr, parsed.log_syslog)

    wipe(parsed.disk)


def main():
    progfiguration_error_handler(main_implementation, *sys.argv)
