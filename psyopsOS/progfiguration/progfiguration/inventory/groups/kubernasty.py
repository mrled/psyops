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
            "wholedisks": [WholeDiskSpec()],
            "partitions": [
                PartitionSpec(
                    "/sys/devices/pci0000:00/0000:00:17.0/ata1/host0/target0:0:0/0:0:0:0/block/sda",
                    "psyopsosdata",
                    "0%",
                    "100%",
                    volgroup="psyopsos_datadiskvg",
                    encrypt=True,
                ),
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
