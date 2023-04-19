from pathlib import Path

from progfiguration.inventory.roles import RoleResultReference
from progfiguration.localhost.disks import (
    FilesystemSpec,
    LvmLvSpec,
    PartitionSpec,
    WholeDiskSpec,
)
from progfiguration.progfigtypes import Bunch


group = Bunch(
    roles=Bunch(
        blockdevparty={
            "wholedisks": [
                # Currently unused
                WholeDiskSpec("/dev/nvme0n1", None, None, False),
            ],
            "partitions": [
                PartitionSpec("/dev/sda", "psyopsosdata", "0%", "100%", volgroup="psyopsos_datadiskvg", encrypt=True),
            ],
            "volumes": [
                LvmLvSpec("datadisklv", "psyopsos_datadiskvg", r"100%FREE", FilesystemSpec("ext4", "psyopsos_data")),
            ],
        },
        acmeupdater_base={
            "role_dir": Path("/psyopsos-data/roles/acmeupdater"),
            "acme_email": "psyops@micahrl.com",
        },
        acmeupdater_synology={
            "capthook_hooksdir": RoleResultReference("capthook", "hooksdir"),
        },
    ),
)
