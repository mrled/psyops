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


all_architectures = {
    "x86_64": Architecture("x86_64", "x86_64", "x86_64", "amd64", "x86_64", "x86_64"),
    "aarch64": Architecture("aarch64", "aarch64", "arm64", "arm64", "aarch64", "aarch64"),
}
