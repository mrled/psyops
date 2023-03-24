"""My home k3s cluster"""

from progfiguration.inventory.invhelpers import Bunch
from progfiguration.localhost.disks import (
    FilesystemSpec,
    LvmLvSpec,
    PartitionSpec,
    WholeDiskSpec,
)

group = Bunch(
    roles=Bunch(
        blockdevparty={
            "wholedisks": [
                # This is a no-op, but we use this disk for Rook Ceph so we list it here
                WholeDiskSpec("/dev/nvme0n1", None, None, False),
            ],
            "partitions": [
                PartitionSpec("/dev/sda", "psyopsosdata", "0%", "100%", volgroup="psyopsos_datadiskvg", encrypt=True),
            ],
            "volumes": [
                LvmLvSpec("datadisklv", "psyopsos_datadiskvg", r"100%FREE", FilesystemSpec("ext4", "psyopsos_data")),
            ],
        },
        k3s={
            "k3s_interface": "psy0",
            "k3s_vipaddress": "192.168.1.200",
            "k3s_interface2": "psy0",
            "k3s_vipaddress2": "192.168.1.201",
        },
    ),
)
