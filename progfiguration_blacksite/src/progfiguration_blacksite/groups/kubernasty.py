"""My home k3s cluster"""

from progfiguration.localhost.disks import (
    FilesystemSpec,
    LvmLvSpec,
    PartitionSpec,
    WholeDiskSpec,
)
from progfiguration.sitehelpers.agesecrets import AgeSecretReference

group = dict(
    roles=dict(
        blockdevparty={
            "wholedisks": [
                # This is a no-op, but we use this disk for Rook Ceph so we list it here
                WholeDiskSpec("/dev/nvme0n1", None, None, False),
            ],
            "partitions": [
                PartitionSpec(
                    "/dev/sda",
                    "psyopsosdata",
                    "0%",
                    "100%",
                    volgroup="psyopsos_datadiskvg",
                    encrypt=True,
                ),
            ],
            "volumes": [
                LvmLvSpec(
                    "datadisklv",
                    "psyopsos_datadiskvg",
                    r"100%FREE",
                    FilesystemSpec("ext4", "psyopsos_data"),
                ),
            ],
        },
        kubernasty={
            "flux_deploy_id": AgeSecretReference("flux_deploy_id"),
            "flux_agekey": AgeSecretReference("flux_agekey"),
            "vrrp_authpass": AgeSecretReference("kubernasty_k0s_vrrp_authpass"),
        },
        k3s={
            "k3s_interface": "psy0",
            "k3s_vipaddress": "192.168.1.200",
            "k3s_interface2": "psy0",
            "k3s_vipaddress2": "192.168.1.201",
        },
    ),
)
