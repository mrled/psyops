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
        alpine_postboot_config={
            "devd": "mdev",
        },
        blockdevparty={
            "wholedisks": [
                WholeDiskSpec(
                    "/dev/disk/by-path/",
                    FilesystemSpec("ext4", "psyopsos_root"),
                    encrypt=True,
                    encrypt_label="psyopsos_root",
                ),
            ],
            "partitions": [
                PartitionSpec(
                    "/dev/nvme0n1", "psyopsosdata", "0%", "256GiB", volgroup="psyopsos_datadiskvg", encrypt=True
                ),
                PartitionSpec("/dev/nvme0n1", "treasure", "256GiB", "100%", encrypt=False),
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
