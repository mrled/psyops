from dataclasses import dataclass

from neuralupgrade.filesystems import Filesystem


@dataclass
class NeuralPartition:
    """A managed partition for either psyopsOS or firmware"""

    fs: Filesystem
    metadata: dict[str, str]


@dataclass
class NeuralPartitionOS(NeuralPartition):
    """Result of a psyops partition operation."""

    fs: Filesystem
    metadata: dict[str, str]
    running: bool
    next_boot: bool


@dataclass
class NeuralPartitionFirmware(NeuralPartition):
    """Result of a psyopsESP operation."""

    fs: Filesystem
    metadata: dict[str, str]
    neuralupgrade_info: dict[str, str]


@dataclass
class SystemMetadata:
    """Result of a system metadata operation."""

    a: NeuralPartitionOS
    b: NeuralPartitionOS
    firmware: NeuralPartitionFirmware
    booted_label: str
    nonbooted_label: str
    nextboot_label: str

    @property
    def by_label(self) -> dict[str, NeuralPartitionOS]:
        """Return the A and B partitions by label."""
        return {self.a.fs.label: self.a, self.b.fs.label: self.b}

    @property
    def booted(self):
        """Return the booted partition."""
        return self.by_label[self.booted_label]

    @property
    def nonbooted(self):
        """Return the nonbooted partition."""
        return self.by_label[self.nonbooted_label]

    @property
    def nextboot(self):
        """Return the nextboot partition."""
        return self.by_label[self.nextboot_label]
