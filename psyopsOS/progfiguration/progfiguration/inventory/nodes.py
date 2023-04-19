"""Nodes managed by progfiguration"""

from dataclasses import dataclass
from typing import Optional

from progfiguration.progfigtypes import Bunch


@dataclass
class InventoryNode:
    """A data structure for an inventory node.

    Encrypted data

    Does not include encrypted data.
    Accessible from all nodes.
    """

    address: str
    user: str
    notes: str
    flavortext: str
    age_pubkey: str
    ssh_host_fingerprint: str
    psy0mac: str
    serial: str
    roles: Bunch
    network_interfaces: Optional[str] = None

    # If this is True, 'progfiguration apply' will refuse to run.
    # Useful for inspecting early state after a reboot during development.
    TESTING_DO_NOT_APPLY: bool = False

    @property
    def known_hosts_entry(self) -> str:
        return f"{self.address} {self.ssh_host_fingerprint}"
