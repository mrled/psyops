from dataclasses import dataclass


@dataclass
class Architecture:
    """A dataclass to represent an architecture"""

    name: str
    """A consistent name that we use in our scripts for the architecture (should match the key in the arch_artifacts dict)"""
    qemu: str
    """The architecture name for QEMU"""
    kernel: str
    """The architecture name for the kernel"""
    docker: str
    """The architecture name in Docker"""
    mkimage: str
    """The architecture name for Alpine's mkimage.sh"""
    python: str
    """The architecture name returned by Python's platform.machine()"""

    def __hash__(self):
        return hash(self.name)


@dataclass
class BootSystem:
    """A boot system"""

    name: str
    """A consistent name that we use in our scripts for the platform"""

    def __hash__(self):
        return hash(self.name)


@dataclass
class Platform:
    """A platform defines an architecture and a boot system"""

    architecture: Architecture
    """The architecture of the platform"""
    bootsystem: BootSystem
    """The boot system of the platform"""

    @property
    def name(self) -> str:
        """The name of the platform"""
        return f"{self.architecture.name}-{self.bootsystem.name}"

    def __hash__(self):
        return hash(self.name)


ARCHITECTURES = {
    "x86_64": Architecture("x86_64", "x86_64", "x86_64", "amd64", "x86_64", "x86_64"),
    "aarch64": Architecture("aarch64", "aarch64", "arm64", "arm64", "aarch64", "aarch64"),
}
"""A map of architecture names to their classes."""


BOOTSYSTEMS = {
    "uefi": BootSystem("uefi"),
    "rpi4uboot": BootSystem("rpi4uboot"),
}
"""A map of boot system names to their classes."""


PLATFORMS = {
    plat.name: plat
    for plat in [
        Platform(ARCHITECTURES["x86_64"], BOOTSYSTEMS["uefi"]),
        Platform(ARCHITECTURES["aarch64"], BOOTSYSTEMS["rpi4uboot"]),
    ]
}
"""A map of platform names to their classes."""
