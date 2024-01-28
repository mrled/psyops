from contextlib import contextmanager
import json
import subprocess
import time

from neuralupgrade import logger


class UmountError(Exception):
    pass


def fstab() -> list[dict]:
    """Return the contents of /etc/fstab as a list of dicts"""
    filesystems = []
    with open("/etc/fstab") as f:
        for line in f.readlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            fs = {}
            (
                fs["device"],
                fs["mountpoint"],
                fs["fstype"],
                fs["options"],
                fs["dump"],
                fs["pass"],
            ) = line.split()
            filesystems.append(fs)
    return filesystems


def umount_retry(mountpoint: str, attempts: int = 2, sleepbetween: int = 1) -> None:
    """Unmount a mountpoint, retrying if it fails."""
    for attempt in range(attempts):
        if not subprocess.run(["mountpoint", "-q", mountpoint]).returncode == 0:
            logger.debug(f"{mountpoint} is not mounted, no need to umount")
            return
        subprocess.run(["umount", "-l", mountpoint])
        if not subprocess.run(["mountpoint", "-q", mountpoint]).returncode == 0:
            logger.debug(f"Umounted {mountpoint} (attempt {attempt + 1}/{attempts})")
            return
        logger.debug(
            f"Umounting {mountpoint} (attempt {attempt + 1}/{attempts}) failed, sleeping for {sleepbetween} seconds"
        )
        time.sleep(sleepbetween)
    raise UmountError(f"Could not umount {mountpoint} after {attempts} attempts")


@contextmanager
def mountfs(label: str) -> str:
    """Mount a filesystem by label, yield the mountpoint, and unmount it when done

    Mounts the filesystem to the mountpoint specified in /etc/fstab.
    - If it's not mounted on entry, it will be mounted rw on entry and unmounted on exit.
    - If it's mounted ro on entry, it will be remounted rw on entry and remounted ro on exit.
    - If it's mounted rw on entry, it will be left mounted rw on exit.
    - If it's mounted to more than one place, or outside of the fstab mountpoint,
      it will be unmounted from all mountpoints on entry and not remounted on exit.
    """
    for fs in fstab():
        if fs["device"] == f"LABEL={label}":
            break
    else:
        raise Exception(f"Could not find {label} in fstab")
    fstab_mountpoint = fs["mountpoint"]

    blkid_L = subprocess.run(["blkid", "-L", label], check=True, capture_output=True)
    devpath = blkid_L.stdout.decode("utf-8").strip()

    # If the device is mounted anywhere aside from the fstab mountpoint
    # and/or is mounted ro, then we unmount it from all mountpoints and remount it rw to the fstab mountpoint.
    # POSIX doesn't allow different permissions like ro and rw for the same device mounted to two separate places,
    # so this is the simplest way to ensure that we can write to the device.
    findmnt_json = subprocess.run(["findmnt", devpath, "--json"], capture_output=True)
    logger.debug(f"findmnt --json {devpath} -> {findmnt_json.stdout.decode('utf-8')}")
    filesystems = []
    if findmnt_json.returncode == 0:
        filesystems = json.loads(findmnt_json.stdout)["filesystems"]

    mounted_rw = mounted_ro = False
    if not filesystems:
        logger.debug(f"Filesystem with label {label} is not mounted anywhere")
    elif len(filesystems) > 1 or filesystems[0]["target"] != fs["mountpoint"]:
        mountpoints = [f["target"] for f in filesystems]
        logger.debug(
            f"Filesystem with label {label} is mounted at least one mountpoint aside from the fstab mountpoint ({mountpoints}), unmounting all and will not remount"
        )
        for mountpoint in mountpoints:
            umount_retry(mountpoint)
    elif len(filesystems) == 1:
        options = filesystems[0]["options"].split(",")
        if "ro" in options:
            mounted_ro = True
        elif "rw" in options:
            mounted_rw = True

    if mounted_ro:
        logger.debug(f"Filesystem with label {label} is mounted ro to {fs['mountpoint']}, remounting rw")
        subprocess.run(["mount", "-o", "rw,remount", fs["mountpoint"]], check=True)
    elif mounted_rw:
        logger.debug(f"Filesystem with label {label} is mounted rw to {fs['mountpoint']}, no need to remount")
    else:
        logger.debug(f"Filesystem with label {label} is not mounted, mounting rw to {fs['mountpoint']}")
        subprocess.run(["mount", "-o", "rw", fs["mountpoint"]], check=True)

    try:
        yield fstab_mountpoint
    finally:
        if mounted_ro:
            logger.debug(f"Remounting filesystem with label {label} ro")
            subprocess.run(["mount", "-o", "ro,remount", fs["mountpoint"]], check=True)
        elif mounted_rw:
            logger.debug(f"Leaving filesystem with label {label} mounted rw")
        else:
            logger.debug(f"Unmounting filesystem with label {label}")
            umount_retry(fs["mountpoint"])
