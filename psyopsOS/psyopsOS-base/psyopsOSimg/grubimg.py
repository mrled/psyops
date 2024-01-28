import os
import subprocess
from psyopsOSimg import logger
from psyopsOSimg.mount import mountfs


class GrubusbUnknownSideError(Exception):
    pass


def bootedside() -> str:
    """Return the booted side of a grubusb device (A or B)"""
    with open("/proc/cmdline") as f:
        cmdline = f.read()
    for arg in cmdline.split():
        if arg.startswith("psyopsos="):
            thisside = arg.split("=")[1]
            logger.debug(f"Booted side is {thisside}")
            return thisside
    raise GrubusbUnknownSideError("Could not determine booted side of grubusb device")


def otherside(side: str) -> str:
    """Given one side of a grubusb image (A or B), return the other side."""
    A = "psyopsOS-A"
    B = "psyopsOS-B"
    if side not in [A, B]:
        raise GrubusbUnknownSideError(f"Unknown side {side}")
    opposite = A if side == B else B
    logger.debug(f"Side {opposite} is opposite {side}")
    return opposite


def write_grubusb_nonbooted_side(tarball: str) -> None:
    """Write to the non-booted side of a grubusb device (A/B updates)"""
    updateside = otherside(bootedside())
    with mountfs(updateside) as mountpoint:
        logger.debug(f"Extracting {tarball} to {mountpoint}")
        subprocess.run(["tar", "-x", "-f", tarball, "-C", mountpoint], check=True)
        logger.debug(f"Finished extracting {tarball} to {mountpoint}")
    with mountfs("PSYOPSOSEFI") as mountpoint:
        logger.debug(f"Updating grub config on {mountpoint}")
        grubcfg = os.path.join(mountpoint, "grub", "grub.cfg")
        doupdate = True
        newcontents = []
        with open(grubcfg, "r") as f:
            for line in f.readlines():
                if line.startswith("set default="):
                    if line == f"set default={bootedside}":
                        doupdate = False
                        break
                    else:
                        newcontents.append(f"set default={updateside}")
                else:
                    newcontents.append(line)
        if doupdate:
            with open(grubcfg, "w") as f:
                f.write("\n".join(newcontents))
            logger.debug(f"Finished grub config on {mountpoint}")
        else:
            logger.debug(f"Grub config on {mountpoint} is already up to date")
