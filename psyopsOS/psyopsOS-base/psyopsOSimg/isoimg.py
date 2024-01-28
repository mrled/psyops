import json
import subprocess

from psyopsOSimg.mount import umount_retry


def lsblk() -> dict:
    """Return the output of `lsblk --json` as a dict.

    WARNING: if a device is mounted to multiple mountpoints, it will only show up once in the output.
    """
    lsblk_proc = subprocess.run(
        ["lsblk", "--output", "PATH,LABEL,MOUNTPOINT", "--json"],
        check=True,
        capture_output=True,
    )
    return json.loads(lsblk_proc.stdout)


def overwrite_iso_bootmedia(isopath: str, progress: bool = False) -> None:
    """Overwrite an ISO image that is written to a removable device like a USB drive.

    This works with ISO psyopsOS images - not grubusb.

    psyopsOS ISO images do not support A/B updates,
    and change the filesystem image that backs the root ramdisk and kernel modloop,
    which means you should probably reboot soon after applying,
    but a bad image or failure during write must be recovered out of band.
    """

    blockdevs = lsblk()["blockdevices"]

    def label_is_psyopsos_boot(label: str) -> bool:
        """Return True if the label is a psyopsOS boot media label.

        Check for old and current labels.
        """
        boot_media_label_fragments = [
            "psyopsos-boot",  # Old 2023
            "psyboot",  # New 2023
        ]
        for fragment in boot_media_label_fragments:
            if fragment in label:
                return True
        return False

    bootmedia = None
    for device in blockdevs:
        # We must use `device.get("label") or ""` not device.get("label", "")`
        # because the latter will return `None` if the key is not found
        # and we need strings.
        devlabel = device.get("label") or ""
        # Look for the iso9660 volume ID that is tagged with our label.
        # An example: 'partition-name: alpine-std psyopsos-boot x86_64'.
        # See the `alpinelabel` argument in tasks.py.
        if not label_is_psyopsos_boot(devlabel):
            continue

        # Make sure we find the main device, not a partition.
        # If the USB drive is /dev/sdq, then lsblk will see that both /dev/sdq and /dev/sdq1 have our volume ID.
        devpath = device.get("path", "") or ""
        if not devpath or not re.match(f"^/dev/[a-zA-Z]+$", devpath):
            continue

        bootmedia = device

    if not bootmedia:
        raise Exception(f"Could not find boot media, maybe it isn't mounted?")

    umount_retry("/.modloop")
    umount_retry(bootmedia["mountpoint"])

    ddcmd = ["dd", f"if={isopath}", f"of={bootmedia['path']}"]
    if not progress:
        ddcmd += ["status=progress"]
    subprocess.run(ddcmd, check=True)
