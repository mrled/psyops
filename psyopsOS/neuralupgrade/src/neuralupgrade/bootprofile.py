"""Boot profiles"""

import os
import platform
from enum import Enum


class UnknownBootMethodError(Exception):
    pass


class BootMethod(str, Enum):
    """The boot method for the system"""

    uefi = "uefi"
    uboot = "uboot"


class BootProfile(str, Enum):
    """A union of the machine and boot method

    Machine names should match platform.machine() output.

    E.g. (x86_64, uefi).
    """

    efipc = ("x86_64", BootMethod.uefi)
    rpiuboot = ("arm64", BootMethod.uboot)

    @classmethod
    def reverse(cls) -> dict[tuple, "BootProfile"]:
        """Reverse the BootProfile enum to a dict of (machine, boot method)"""
        return {v.value: v for v in cls}


def detect_boot_method() -> BootMethod:
    """Detect the boot profile of the system

    Returns:
        BootProfile: The detected boot profile
    """

    # Detecting UEFI is standard on Linux
    if os.path.exists("/sys/firmware/efi"):
        return BootMethod.uefi

    # This path exists on Alpine on Raspberry Pi as of 3.21.3 at least,
    # it doesn't exist on Alpine x86_64 though.
    # Example contents:
    #   Raspberry Pi 4 Model B Rev 1.2localhost
    if os.path.exists("/proc/device-tree/model"):
        with open("/proc/device-tree/model") as f:
            model = f.read()
            if "Raspberry Pi" in model:
                return BootMethod.uboot

    # Detecting U-Boot is not standard;
    # assume all Raspberry Pi systems are U-Boot systems
    #

    raise UnknownBootMethodError


def detect_boot_profile() -> BootProfile:
    """Detect the boot profile of the currently running system

    Returns:
        BootProfile: The detected boot profile
    """
    # Detect the boot method
    boot_method = detect_boot_method()

    # Detect the machine type
    machine = platform.machine()

    # Create the boot profile
    profile = BootProfile.reverse().get((machine, boot_method), None)
    if not profile:
        raise UnknownBootMethodError(f"Unknown boot profile for {machine} and {boot_method}")
    return profile
