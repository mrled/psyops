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
            "wholedisks": [WholeDiskSpec("/dev/nvme0n1", encrypt=True, encrypt_label="nvme0n1_crypt")],
            "partitions": [
                PartitionSpec(
                    "/dev/mapper/nvme0n1_crypt", "psyopsosdata", "0%", "256GiB", volgroup="psyopsos_datadiskvg"
                ),
                PartitionSpec("/dev/mapper/nvme0n1_crypt", "treasure", "256GiB", "100%"),
            ],
            "volumes": [
                LvmLvSpec("datadisklv", "psyopsos_datadiskvg", r"100%FREE", FilesystemSpec("ext4", "psyopsos_data")),
            ],
        },
        datadisk_v2={
            "block_device": "/dev/mapper/psyopsos_datadiskvg-datadisklv",
        },
        k3s={
            "kube_vip_address": "192.168.1.200",
        },
    ),
)
