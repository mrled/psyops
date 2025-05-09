import os
from neuralupgrade.firmware import Firmware
from neuralupgrade.firmware.uefipc import AMD64UEFIGrubBootloader
from neuralupgrade.firmware.rpi import RaspberryPi4UBootBootloader


class UnknownFirmwareError(Exception):
    pass


def detect_firmware() -> Firmware:
    """Detect the firmware of the currently running system"""

    # Detecting UEFI is standard on Linux
    if os.path.exists("/sys/firmware/efi"):
        return AMD64UEFIGrubBootloader()

    # This path exists on Alpine on Raspberry Pi as of 3.21.3 at least,
    # it doesn't exist on Alpine x86_64 though.
    # Example contents:
    #   Raspberry Pi 4 Model B Rev 1.2localhost
    if os.path.exists("/proc/device-tree/model"):
        with open("/proc/device-tree/model") as f:
            model = f.read()
            if "Raspberry Pi" in model:
                return RaspberryPi4UBootBootloader()

    # Detecting U-Boot is not standard;
    # assume all Raspberry Pi systems are U-Boot systems

    raise UnknownFirmwareError


FIRMWARES = [
    AMD64UEFIGrubBootloader,
    RaspberryPi4UBootBootloader,
]
"""A list of all known firmware classes."""


FirmwareTypeMap = {fw.fwtype: fw for fw in FIRMWARES}
"""A map of firmware type names to their classes."""
