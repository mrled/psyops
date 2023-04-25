"""The universal group

This is not a normal group.
Membership is automatic for all nodes,
and role arguments and secrets from the universal group always apply first,
while other groups have no guarantee of order.
"""

from progfiguration.age import AgeSecretReference
from progfiguration.localhost.disks import (
    FilesystemSpec,
    LvmLvSpec,
    PartitionSpec,
    WholeDiskSpec,
)
from progfiguration.progfigtypes import Bunch

group = Bunch(
    testattribute="test value",
    roles=Bunch(
        alpine_postboot_config={
            "timezone": "US/Central",
        },
        blockdevparty={
            # For the simple case of a single disk that is wholly dedicated to psyopsos_datadiskvg-datadisklv,
            # individual nodes can override just this `wholedisks` argument with a path to their block device.
            # As long as it has the label `data_crypt`, the `partitions` and `volumes` here will work.
            # In more complex scenarios, nodes can override all 3.
            "wholedisks": [WholeDiskSpec("/dev/sda", encrypt=True, encrypt_label="data_crypt")],
            # WARNING:  progfiguration cannot find partitions created on cryptsetup devices,
            #           even though those are valid as far as I can tell.
            #           Instead of encrypting a whole disk and then partitioning the encrypted wrapper,
            #           partition the whole disk and encrypt each partition separately.
            #
            # For the first partition, you want to use '0%' rather than '0' or '0s' so that it aligns properly.
            # If you pass percentages, parted will automatically handle alignment.
            # If you pass absolute units, it may not do so - it may try to follow the absolute too strictly.
            # Alignment only matters for the start - if the end is not aligned, this has ~0 performance impact.
            "partitions": [
                PartitionSpec("/dev/mapper/data_crypt", "psyopsosdata", "0%", "100%", volgroup="psyopsos_datadiskvg"),
            ],
            "volumes": [
                LvmLvSpec("datadisklv", "psyopsos_datadiskvg", r"100%FREE", FilesystemSpec("ext4", "psyopsos_data")),
            ],
        },
        datadisk_v2={
            "block_device": "/dev/mapper/psyopsos_datadiskvg-datadisklv",
        },
        emailfwd={
            "smtp_host": "smtps-proxy.messagingengine.com",
            "smtp_port": 443,
            "smtp_user": "mrled@fastmail.com",
            "smtp_pass": AgeSecretReference("emailfwd_smtp_pass"),
            "from_addr": "psyops@micahrl.com",
            "aliases": {
                # My own inbox, for top priority stuff
                "micahrl": "me@micahrl.com",
                # The psyops inbox, for everything else
                "default": "psyops@micahrl.com",
            },
        },
    ),
)
