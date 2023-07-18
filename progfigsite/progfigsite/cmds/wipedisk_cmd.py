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
from progfiguration.localhost import disks as localhost_disks
from progfiguration import logger


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


def get_vgs() -> Dict[str, str]:
    """Get LVM volume groups"""
    p = subprocess.run(["vgs", "--reportformat", "json"], check=True, capture_output=True)
    output = json.loads(p.stdout)
    return [vg["vg_name"] for vg in output["report"][0]["vg"]]


def get_lvs() -> Dict[str, str]:
    """Get LVM logical volumes"""
    p = subprocess.run(["lvs", "--reportformat", "json"], check=True, capture_output=True)
    output = json.loads(p.stdout)
    result = []
    for lv in output["report"][0]["lv"]:
        lvname = lv["lv_name"]
        vgname = lv["vg_name"]
        devname = f"{vgname}-{lvname}"
        path = f"/dev/mapper/{devname}"
        result.append({"lv": lvname, "vg": vgname, "devname": devname, "devpath": path})
    return result


def wipe(disks: List[str], _lvs=None, _vgs=None):
    """Wipe a block device

    disks: list of block devices to wipe
    _lvs:  result of get_lvs(); internal use only
    _vgs:  result of get_vgs(); internal use only
    """

    if _lvs is None:
        _lvs = get_lvs()
    if _vgs is None:
        _vgs = get_vgs()

    # This list may contain vgs that still have active lvs on them after we finish,
    # so we can't assume that everything in this list can actually be removed.
    vgs_to_remove = []

    for disk in disks:
        disk_path = resolve_disk(disk)
        blk = lsblk(disk_path)
        for found_device in blk["blockdevices"]:
            children = found_device.get("children", [])
            for child in children:
                wipe([child["name"]], _lvs=_lvs, _vgs=_vgs)

            if "mountpoints" in found_device:
                failed_umounts = []
                for mp in [m for m in found_device["mountpoints"] if m]:
                    try:
                        subprocess.run(["umount", mp], check=True)
                    except subprocess.CalledProcessError:
                        failed_umounts.append(mp)
                for mp in failed_umounts:
                    try:
                        subprocess.run(["umount", "-l", mp], check=True)
                    except subprocess.CalledProcessError:
                        raise ProgfigurationTerminalError(
                            f"Got an error trying to lazily unmount {found_device['name']} from mountpoint {mp}; you may also want to check other mountpoints in this list: {failed_umounts}",
                            1,
                        )
                for mp in failed_umounts:
                    if localhost_disks.is_mountpoint(mp):
                        raise ProgfigurationTerminalError(
                            f"Tried to lazily unmount {found_device['name']} from mountpoint {mp}, but it's still mounted; you probably need to `lsof -w +D {mp}` and kill those processes; you may also want to check other mountpoints in this list: {failed_umounts}",
                            1,
                        )

            # Unfortunately lsblk's "name" field for a device doesn't include the full path, smh
            found_device_path = resolve_disk(found_device["name"])

            if found_device["type"] == "disk":
                subprocess.run(["wipefs", "--all", found_device_path], check=True)
            elif found_device["type"] == "part":
                subprocess.run(["wipefs", "--all", found_device_path], check=True)
            elif found_device["type"] == "crypt":
                subprocess.run(["cryptsetup", "close", found_device["name"]], check=True)
            elif found_device["type"] == "lvm":
                for lv in _lvs:
                    if lv["devname"] == found_device["name"]:
                        subprocess.run(["lvchange", "-an", lv["devpath"]], check=True)
                        subprocess.run(["lvremove", lv["devpath"]], check=True)
            else:
                raise Exception(f"Unknown type {found_device['type']} for device {found_device['name']}.")

    # If all the lvs in a vg are gone, this should succeed.
    # If there are still lvs in a vg, this will fail.
    # We'll just cowboy up and ignore any failures, lol.
    for vg in vgs_to_remove:
        vgcresult = subprocess.run(["vgchange", "-an", vg], check=False)
        succeeded = vgcresult.returncode == 0
        if succeeded:
            vgrresult = subprocess.run(["vgremove", vg], check=False)
            succeeded = vgrresult.returncode == 0
        if not succeeded:
            logger.warning(
                f"Failed to remove vg {vg}. If this vg has lvs that you want to keep, then this is correct; otherwise, you may want to remove it manually."
            )


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
