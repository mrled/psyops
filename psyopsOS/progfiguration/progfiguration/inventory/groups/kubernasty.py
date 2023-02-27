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
            "wholedisks": [],
            "partitions": [
                PartitionSpec(
                    "/dev/nvme0n1", "psyopsosdata", "0%", "256GiB", volgroup="psyopsos_datadiskvg", encrypt=True
                ),
                PartitionSpec("/dev/nvme0n1", "treasure", "256GiB", "100%", encrypt=True),
            ],
            "volumes": [
                LvmLvSpec("datadisklv", "psyopsos_datadiskvg", r"100%FREE", FilesystemSpec("ext4", "psyopsos_data")),
            ],
        },
        k3s={
            # "kube_vip_address": "192.168.1.200",
        },
    ),
)
